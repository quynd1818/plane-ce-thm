from uuid import uuid4
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from plane.db.models import (
    Issue,
    IssueActivity,
    Project,
    ProjectCustomProperty,
    ProjectCustomRole,
    ProjectMember,
    ProjectRoleAssignment,
    User,
    WorkLog,
    WorkspaceMember,
)


@pytest.fixture
def rbac(db, workspace, create_user):
    project = Project.objects.create(
        name="Role project", identifier="RBAC", workspace=workspace, is_time_tracking_enabled=True
    )
    ProjectMember.objects.create(project=project, member=create_user, role=20)
    user = User.objects.create(email="restricted@plane.so", username="restricted")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15)
    member = ProjectMember.objects.create(project=project, member=user, role=15)
    issue = Issue.objects.create(
        project=project, workspace=workspace, name="Contract", custom_properties={"legal": "old", "finance": 10}
    )
    ProjectCustomProperty.objects.create(project=project, key="legal", name="Legal", property_type="text")
    ProjectCustomProperty.objects.create(project=project, key="finance", name="Finance", property_type="number")
    role = ProjectCustomRole.objects.create(
        project=project, name="Accounting", permissions=["worklogs.read", "worklogs.export"]
    )
    assignment = ProjectRoleAssignment.objects.create(project=project, membership=member, custom_role=role)
    client, admin = APIClient(), APIClient()
    client.force_authenticate(user=user)
    admin.force_authenticate(user=create_user)
    base = f"/api/workspaces/{workspace.slug}/projects/{project.id}/"
    return {
        "project": project,
        "user": user,
        "member": member,
        "issue": issue,
        "role": role,
        "assignment": assignment,
        "client": client,
        "admin": admin,
        "base": base,
        "workspace": workspace,
    }


def legal_role(rbac):
    role = rbac["role"]
    role.permissions = ["properties.read", "properties.edit"]
    role.property_keys = ["legal"]
    role.save()


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectRoles:
    def test_accounting_report_and_csv(self, rbac):
        WorkLog.objects.create(
            project=rbac["project"],
            issue=rbac["issue"],
            user=rbac["user"],
            started_at=timezone.now() - timedelta(hours=1),
            ended_at=timezone.now(),
            duration_seconds=3600,
            description="review",
        )
        response = rbac["client"].get(rbac["base"] + "worklogs/report/")
        assert response.status_code == 200
        assert response.data["total_seconds"] == 3600
        response = rbac["client"].get(rbac["base"] + "worklogs/report/?format=csv")
        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/csv")
        assert b"review" in response.content

    def test_export_requires_separate_permission(self, rbac):
        rbac["role"].permissions = ["worklogs.read"]
        rbac["role"].save()
        assert rbac["client"].get(rbac["base"] + "worklogs/report/").status_code == 200
        assert rbac["client"].get(rbac["base"] + "worklogs/report/?format=csv").status_code == 403

    @pytest.mark.parametrize(
        "method,path,payload",
        [
            ("get", "issues/", None),
            ("get", "pages/", None),
            ("get", "role-issues/", None),
            ("post", "issues/", {"name": "Bypass"}),
            ("post", "custom-properties/", {"name": "New", "key": "new"}),
            ("get", "custom-roles/", None),
            ("post", "custom-roles/", {"name": "Elevated", "permissions": ["issues.read"]}),
        ],
    )
    def test_accounting_cannot_access_other_features(self, rbac, method, path, payload):
        response = getattr(rbac["client"], method)(rbac["base"] + path, payload, format="json")
        assert response.status_code == 403

    @pytest.mark.parametrize(
        "method,suffix,payload",
        [
            ("patch", "", {"name": "Bypass"}),
            ("patch", "", {"custom_properties": {"finance": 100}}),
            ("delete", "", {}),
            ("post", "worklogs/", {"duration_seconds": 100}),
            ("post", "timer/", {}),
        ],
    )
    def test_direct_mutations_are_denied(self, rbac, method, suffix, payload):
        url = rbac["base"] + f"issues/{rbac['issue'].id}/" + suffix
        assert getattr(rbac["client"], method)(url, payload, format="json").status_code == 403

    def test_legal_edits_only_allowed_property_preserving_other_values(self, rbac):
        legal_role(rbac)
        response = rbac["client"].get(rbac["base"] + "role-issues/")
        assert response.status_code == 200
        assert "description_html" not in response.data["results"][0]
        response = rbac["client"].patch(
            rbac["base"] + f"role-issues/{rbac['issue'].id}/",
            {"custom_properties": {"legal": "approved"}},
            format="json",
        )
        assert response.status_code == 200
        rbac["issue"].refresh_from_db()
        assert rbac["issue"].custom_properties == {"legal": "approved", "finance": 10}
        assert IssueActivity.objects.filter(issue=rbac["issue"], actor=rbac["user"], field="custom_properties").exists()

    @pytest.mark.parametrize(
        "payload,expected",
        [
            ({"custom_properties": {"finance": 900}}, 403),
            ({"custom_properties": {"legal": "changed", "finance": 900}}, 403),
            ({"custom_properties": {"legal": "changed"}, "state_id": None}, 400),
            ({"custom_properties": None}, 400),
            ({"custom_properties": {"legal": 123}}, 400),
        ],
    )
    def test_legal_rejects_unauthorized_or_invalid_changes(self, rbac, payload, expected):
        legal_role(rbac)
        response = rbac["client"].patch(rbac["base"] + f"role-issues/{rbac['issue'].id}/", payload, format="json")
        assert response.status_code == expected
        rbac["issue"].refresh_from_db()
        assert rbac["issue"].custom_properties == {"legal": "old", "finance": 10}

    def test_disabled_and_deleted_roles_fail_closed(self, rbac):
        rbac["role"].is_active = False
        rbac["role"].save()
        assert rbac["client"].get(rbac["base"] + "worklogs/report/").status_code == 403
        me = rbac["client"].get(rbac["base"] + "custom-role/me/")
        assert me.status_code == 200 and me.data["restricted"] and me.data["role"]["permissions"] == []
        ProjectCustomRole.objects.filter(pk=rbac["role"].pk).update(is_active=True, deleted_at=timezone.now())
        assert rbac["client"].get(rbac["base"] + "worklogs/report/").status_code == 403

    def test_revocation_applies_next_request(self, rbac):
        assert rbac["client"].get(rbac["base"] + "worklogs/report/").status_code == 200
        response = rbac["admin"].patch(
            rbac["base"] + f"custom-roles/{rbac['role'].id}/", {"permissions": []}, format="json"
        )
        assert response.status_code == 200
        assert rbac["client"].get(rbac["base"] + "worklogs/report/").status_code == 403

    def test_cannot_delete_assigned_role_or_remove_own_restriction(self, rbac):
        url = rbac["base"] + f"custom-roles/{rbac['role'].id}/"
        assert rbac["admin"].delete(url).status_code == 409
        assign = rbac["base"] + f"role-assignments/{rbac['member'].id}/"
        assert rbac["client"].put(assign, {"custom_role_id": None}, format="json").status_code == 403
        assert rbac["admin"].put(assign, {"custom_role_id": None}, format="json").status_code == 200
        assert rbac["client"].get(rbac["base"] + "custom-role/me/").data["restricted"] is False
        assert rbac["admin"].delete(url).status_code == 204

    def test_role_assignment_cannot_cross_project(self, rbac):
        other = Project.objects.create(workspace=rbac["workspace"], name="Other", identifier="OTHER")
        other_role = ProjectCustomRole.objects.create(project=other, name="Other role")
        url = rbac["base"] + f"role-assignments/{rbac['member'].id}/"
        assert rbac["admin"].put(url, {"custom_role_id": str(other_role.id)}, format="json").status_code == 404

    def test_cannot_restrict_admin_or_guest(self, rbac):
        url = rbac["base"] + f"role-assignments/{rbac['member'].id}/"
        for role in (5,):
            ProjectMember.objects.filter(pk=rbac["member"].pk).update(role=role)
            assert rbac["admin"].put(url, {"custom_role_id": str(rbac["role"].id)}, format="json").status_code == 400

    def test_unassigned_admin_unaffected(self, rbac):
        assert rbac["admin"].get(rbac["base"] + "custom-roles/").status_code == 200
        assert rbac["admin"].get(rbac["base"] + "custom-role/me/").data["restricted"] is False

    @pytest.mark.parametrize(
        "payload",
        [
            {"name": "Invalid", "permissions": ["admin"]},
            {"name": "Invalid", "permissions": ["worklogs.export"]},
            {"name": "Invalid", "permissions": ["properties.edit"]},
            {"name": "Invalid", "permissions": ["properties.read", "properties.edit"], "property_keys": ["other"]},
        ],
    )
    def test_role_configuration_validation(self, rbac, payload):
        assert rbac["admin"].post(rbac["base"] + "custom-roles/", payload, format="json").status_code == 400

    def test_workspace_aggregate_and_export_denied(self, rbac):
        slug = rbac["workspace"].slug
        from plane.app.views.exporter.base import ExportIssuesEndpoint
        from rest_framework.test import APIRequestFactory, force_authenticate

        factory = APIRequestFactory()
        request = factory.post(
            f"/api/workspaces/{slug}/export-issues/",
            {"project": [str(rbac["project"].id)], "provider": "csv"},
            format="json",
        )
        force_authenticate(request, user=rbac["user"])
        assert ExportIssuesEndpoint.as_view()(request, slug=slug).status_code == 403

    def test_public_api_token_cannot_bypass_role(self, rbac):
        from plane.db.models import APIToken

        token = APIToken.objects.create(user=rbac["user"], label="restricted", token=uuid4().hex)
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=token.token)
        base = rbac["base"].replace("/api/", "/api/v1/")
        assert client.get(base + "issues/").status_code == 403
        assert client.patch(base + f"issues/{rbac['issue'].id}/", {"name": "Bypass"}, format="json").status_code == 403

    def test_property_target_cannot_cross_project(self, rbac):
        legal_role(rbac)
        other = Project.objects.create(workspace=rbac["workspace"], name="Other", identifier="OTHER")
        issue = Issue.objects.create(project=other, name="Hidden")
        assert (
            rbac["client"]
            .patch(rbac["base"] + f"role-issues/{issue.id}/", {"custom_properties": {"legal": "x"}}, format="json")
            .status_code
            == 404
        )

    def test_membership_revoked(self, rbac):
        WorkspaceMember.objects.filter(workspace=rbac["workspace"], member=rbac["user"]).update(is_active=False)
        assert rbac["client"].get(rbac["base"] + "worklogs/report/").status_code == 403

    def test_unassigned_project_keeps_its_builtin_permissions(self, rbac):
        other = Project.objects.create(workspace=rbac["workspace"], name="Other", identifier="OTHER")
        ProjectMember.objects.create(project=other, member=rbac["user"], role=20)
        base = rbac["base"].replace(str(rbac["project"].id), str(other.id))
        assert rbac["client"].get(base + "issues/").status_code == 200
        assert rbac["client"].get(base + "worklogs/report/").status_code == 200

    def test_workspace_entry_displays_role_without_aggregate_data(self, rbac):
        response = rbac["client"].get(f"/api/workspaces/{rbac['workspace'].slug}/role-access/")
        assert response.status_code == 200
        assert response.data["restricted"] is True
        assert response.data["projects"][0]["role"]["name"] == "Accounting"

    def test_inactive_membership_does_not_restore_workspace_access(self, rbac):
        ProjectMember.objects.filter(pk=rbac["member"].pk).update(is_active=False)
        assert rbac["client"].get(rbac["base"] + "worklogs/report/").status_code == 403
        url = rbac["base"] + f"role-assignments/{rbac['member'].id}/"
        assert rbac["admin"].put(url, {"custom_role_id": None}, format="json").status_code == 200
        assert not ProjectRoleAssignment.all_objects.filter(membership=rbac["member"]).exists()

    def test_spreadsheet_formula_is_not_executable(self, rbac):
        WorkLog.objects.create(
            project=rbac["project"],
            issue=rbac["issue"],
            user=rbac["user"],
            started_at=timezone.now(),
            duration_seconds=60,
            description="=1+2",
        )
        response = rbac["client"].get(rbac["base"] + "worklogs/report/?format=csv")
        assert response.status_code == 200
        assert b"'=1+2" in response.content

    def test_admin_can_reassign_after_removing_assignment(self, rbac):
        url = rbac["base"] + f"role-assignments/{rbac['member'].id}/"
        assert rbac["admin"].put(url, {"custom_role_id": None}, format="json").status_code == 200
        assert rbac["admin"].put(url, {"custom_role_id": str(rbac["role"].id)}, format="json").status_code == 200
        assert rbac["client"].get(rbac["base"] + "custom-role/me/").data["restricted"] is True

    def test_admin_creates_and_assigns_legal_role(self, rbac):
        response = rbac["admin"].post(
            rbac["base"] + "custom-roles/",
            {
                "name": "Legal",
                "permissions": ["properties.read", "properties.edit"],
                "property_keys": ["legal"],
            },
            format="json",
        )
        assert response.status_code == 201
        role_id = str(response.data["id"])
        response = rbac["admin"].put(
            rbac["base"] + f"role-assignments/{rbac['member'].id}/", {"custom_role_id": role_id}, format="json"
        )
        assert response.status_code == 200
        me = rbac["client"].get(rbac["base"] + "custom-role/me/")
        assert me.data["role"]["id"] == role_id
        assert me.data["role"]["property_keys"] == ["legal"]

    def test_soft_deleted_assignment_remains_restricted_until_explicit_removal(self, rbac):
        ProjectRoleAssignment.objects.filter(pk=rbac["assignment"].pk).update(deleted_at=timezone.now())
        assert rbac["client"].get(rbac["base"] + "issues/").status_code == 403
        url = rbac["base"] + f"role-assignments/{rbac['member'].id}/"
        assert rbac["admin"].put(url, {"custom_role_id": None}, format="json").status_code == 200
        assert rbac["client"].get(rbac["base"] + "custom-role/me/").data["restricted"] is False

    def test_cannot_assign_inactive_membership(self, rbac):
        ProjectMember.objects.filter(pk=rbac["member"].pk).update(is_active=False)
        url = rbac["base"] + f"role-assignments/{rbac['member'].id}/"
        assert rbac["admin"].put(url, {"custom_role_id": str(rbac["role"].id)}, format="json").status_code == 400

    @pytest.mark.parametrize(
        "resource,path,payload",
        [
            ("issues", "issues/", {"name": "New work item"}),
            ("cycles", "cycles/", {"name": "New cycle"}),
            ("modules", "modules/", {"name": "New module"}),
            ("pages", "pages/", {"name": "New page", "access": 0}),
            ("views", "views/", {"name": "New view", "filters": {}}),
        ],
    )
    def test_feature_read_and_create_are_separate(self, rbac, resource, path, payload):
        role = rbac["role"]
        role.permissions = [f"{resource}.read"]
        role.save()
        assert rbac["client"].get(rbac["base"] + path).status_code == 200
        assert rbac["client"].post(rbac["base"] + path, payload, format="json").status_code == 403
        role.permissions.append(f"{resource}.create")
        role.save()
        response = rbac["client"].post(rbac["base"] + path, payload, format="json")
        assert response.status_code == 201, response.data

    def test_workspace_search_filters_only_restricted_project(self, rbac):
        other = Project.objects.create(workspace=rbac["workspace"], name="Other", identifier="OTHER")
        ProjectMember.objects.create(project=other, member=rbac["user"], role=15)
        visible = Issue.objects.create(project=other, name="Visible contract")
        url = f"/api/workspaces/{rbac['workspace'].slug}/search/?entities=issue&workspace_search=true"
        response = rbac["client"].get(url)
        assert response.status_code == 200, response.data
        ids = [str(i["id"]) for i in response.data["results"]["issue"]]
        assert str(visible.id) in ids
        assert str(rbac["issue"].id) not in ids
        rbac["role"].permissions = ["issues.read"]
        rbac["role"].save()
        response = rbac["client"].get(url)
        assert str(rbac["issue"].id) in [str(i["id"]) for i in response.data["results"]["issue"]]

    def test_public_api_read_does_not_grant_update(self, rbac):
        from plane.db.models import APIToken

        role = rbac["role"]
        role.permissions = ["issues.read"]
        role.save()
        token = APIToken.objects.create(user=rbac["user"], label="reader", token=uuid4().hex)
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=token.token)
        base = rbac["base"].replace("/api/", "/api/v1/")
        assert client.get(base + "issues/").status_code == 200
        url = base + f"issues/{rbac['issue'].id}/"
        assert client.patch(url, {"name": "Denied"}, format="json").status_code == 403
        role.permissions.append("issues.update")
        role.save()
        response = client.patch(url, {"name": "Allowed"}, format="json")
        assert response.status_code == 200, response.data

    def test_standard_issue_api_enforces_property_keys(self, rbac):
        role = rbac["role"]
        role.permissions = ["issues.read", "issues.update", "properties.read", "properties.edit"]
        role.property_keys = ["legal"]
        role.save()
        url = rbac["base"] + f"issues/{rbac['issue'].id}/"
        assert rbac["client"].patch(url, {"custom_properties": {"finance": 99}}, format="json").status_code == 403
        response = rbac["client"].patch(url, {"custom_properties": {"legal": "approved"}}, format="json")
        assert response.status_code == 204, response.data
        rbac["issue"].refresh_from_db()
        assert rbac["issue"].custom_properties == {"legal": "approved", "finance": 10}

    def test_analytics_filters_before_counting_outside_request_context(self, rbac):
        from plane.utils.dashboard import base_issue_queryset

        other = Project.objects.create(workspace=rbac["workspace"], name="Other", identifier="OTHER")
        ProjectMember.objects.create(project=other, member=rbac["user"], role=15)
        issue = Issue.objects.create(project=other, name="Visible")
        qs = base_issue_queryset(rbac["workspace"].id, rbac["user"], None, {})
        assert list(qs.values_list("id", flat=True)) == [issue.id]
        rbac["role"].permissions = ["issues.read", "analytics.read"]
        rbac["role"].save()
        assert base_issue_queryset(rbac["workspace"].id, rbac["user"], None, {}).count() == 2

    def test_cross_project_relation_requires_both_projects(self, rbac):
        other = Project.objects.create(workspace=rbac["workspace"], name="Other", identifier="OTHER")
        ProjectMember.objects.create(project=other, member=rbac["user"], role=15)
        issue = Issue.objects.create(project=other, name="Visible")
        base = rbac["base"].replace(str(rbac["project"].id), str(other.id))
        response = rbac["client"].patch(base + f"issues/{issue.id}/", {"parent": str(rbac["issue"].id)}, format="json")
        assert response.status_code == 403
        # A URL for an unrestricted project cannot be used with a restricted object's ID.
        response = rbac["client"].patch(base + f"issues/{rbac['issue'].id}/", {"name": "Bypass"}, format="json")
        assert response.status_code == 404

    def test_project_admin_may_be_restricted_but_cannot_manage_own_role(self, rbac):
        ProjectMember.objects.filter(pk=rbac["member"].pk).update(role=20)
        url = rbac["base"] + f"role-assignments/{rbac['member'].id}/"
        assert rbac["admin"].put(url, {"custom_role_id": str(rbac["role"].id)}, format="json").status_code == 200
        assert rbac["client"].put(url, {"custom_role_id": None}, format="json").status_code == 403
        WorkspaceMember.objects.filter(workspace=rbac["workspace"], member=rbac["user"]).update(role=20)
        assert rbac["admin"].put(url, {"custom_role_id": str(rbac["role"].id)}, format="json").status_code == 400

    def test_page_update_cannot_bypass_share_lock_permissions(self, rbac):
        from plane.db.models import Page, ProjectPage

        page = Page.objects.create(workspace=rbac["workspace"], name="Page", owned_by=rbac["user"])
        ProjectPage.objects.create(project=rbac["project"], page=page, workspace=rbac["workspace"])
        rbac["role"].permissions = ["pages.read", "pages.update"]
        rbac["role"].save()
        url = rbac["base"] + f"pages/{page.id}/"
        for payload in ({"access": 1 - page.access}, {"is_locked": True}, {"archived_at": timezone.now().isoformat()}):
            assert rbac["client"].patch(url, payload, format="json").status_code == 403

    def test_context_clears_and_revocation_is_not_cached(self, rbac):
        from plane.utils.project_rbac_scope import current_role_request

        rbac["role"].permissions = ["issues.read"]
        rbac["role"].save()
        response = rbac["client"].get(rbac["base"] + "issues/")
        assert response.status_code == 200
        assert response["Cache-Control"] == "private, no-store"
        assert current_role_request.get() is None
        rbac["role"].permissions = []
        rbac["role"].save()
        assert rbac["client"].get(rbac["base"] + "issues/").status_code == 403
        assert current_role_request.get() is None

    def test_every_project_route_has_an_explicit_policy(self):
        from django.urls import get_resolver, URLResolver
        from plane.utils.project_rbac_policies import POLICIES

        reserved = {"ProjectCustomRoleEndpoint", "ProjectCustomRoleDetailEndpoint", "ProjectRoleAssignmentEndpoint"}

        def walk(patterns, prefix=""):
            for pattern in patterns:
                path = prefix + str(pattern.pattern)
                if isinstance(pattern, URLResolver):
                    walk(pattern.url_patterns, path)
                elif "<uuid:project_id>" in path:
                    view = getattr(pattern.callback, "cls", None)
                    if view and view.__module__.startswith(("plane.app.", "plane.api.")):
                        key = f"{view.__module__}.{view.__name__}"
                        assert key in POLICIES or getattr(view, "rbac_policy", None) or view.__name__ in reserved, path

        walk(get_resolver().url_patterns)

    def test_legacy_property_permission_migration(self, rbac):
        from importlib import import_module
        from django.apps import apps
        from django.db import connection

        migration = import_module("plane.db.migrations.0134_expand_project_role_permissions")
        rbac["role"].permissions = ["issues.read", "properties.edit"]
        rbac["role"].save()
        with connection.schema_editor() as editor:
            migration.forwards(apps, editor)
        rbac["role"].refresh_from_db()
        assert set(rbac["role"].permissions) == {"properties.read", "properties.edit"}

    def test_live_editor_access_and_export_are_independently_authorized(self, rbac):
        from plane.db.models import Page, ProjectPage

        page = Page.objects.create(workspace=rbac["workspace"], name="Live page", owned_by=rbac["user"])
        ProjectPage.objects.create(project=rbac["project"], page=page, workspace=rbac["workspace"])
        role = rbac["role"]
        role.permissions = ["pages.read"]
        role.save()
        url = rbac["base"] + f"pages/{page.id}/access-check/"
        assert rbac["client"].get(url).data == {"can_edit": False}
        assert rbac["client"].get(url + "?action=export").status_code == 403
        role.permissions += ["pages.update", "pages.export"]
        role.save()
        assert rbac["client"].get(url).data == {"can_edit": True}
        assert rbac["client"].get(url + "?action=export").status_code == 200
        Page.objects.filter(pk=page.pk).update(is_locked=True)
        assert rbac["client"].get(url).data == {"can_edit": False}

    def test_default_export_includes_only_allowed_projects(self, rbac, mocker):
        from plane.app.views.exporter.base import ExportIssuesEndpoint
        from rest_framework.test import APIRequestFactory, force_authenticate
        from plane.db.models import ExporterHistory

        other = Project.objects.create(workspace=rbac["workspace"], name="Other", identifier="OTHER")
        ProjectMember.objects.create(project=other, member=rbac["user"], role=15)
        mocker.patch("plane.app.views.exporter.base.issue_export_task.delay")
        request = APIRequestFactory().post("/export/", {"provider": "csv"}, format="json")
        force_authenticate(request, user=rbac["user"])
        response = ExportIssuesEndpoint.as_view()(request, slug=rbac["workspace"].slug)
        assert response.status_code == 200
        assert ExporterHistory.objects.get(initiated_by=rbac["user"]).project == [other.id]

    def test_background_export_rechecks_revoked_permissions(self, rbac, mocker):
        from plane.bgtasks.export_task import issue_export_task
        from plane.db.models import ExporterHistory

        exporter = ExporterHistory.objects.create(
            workspace=rbac["workspace"],
            project=[rbac["project"].id],
            initiated_by=rbac["user"],
            provider="csv",
            type="issue_exports",
        )
        upload = mocker.patch("plane.bgtasks.export_task.upload_to_s3")
        issue_export_task(
            "csv", rbac["workspace"].id, [str(rbac["project"].id)], exporter.token, False, rbac["workspace"].slug
        )
        exporter.refresh_from_db()
        assert exporter.status == "failed"
        upload.assert_not_called()

    def test_cycle_counts_do_not_reveal_unreadable_work_items(self, rbac):
        from plane.db.models import Cycle, CycleIssue

        cycle = Cycle.objects.create(project=rbac["project"], name="Cycle", owned_by=rbac["user"])
        CycleIssue.objects.create(project=rbac["project"], issue=rbac["issue"], cycle=cycle)
        rbac["role"].permissions = ["cycles.read"]
        rbac["role"].save()
        response = rbac["client"].get(rbac["base"] + f"cycles/{cycle.id}/")
        assert response.status_code == 200, response.data
        assert response.data["total_issues"] == 0

    def test_shared_page_mutation_requires_permission_in_each_affected_project(self, rbac):
        from plane.db.models import Page, ProjectPage

        other = Project.objects.create(workspace=rbac["workspace"], name="Other", identifier="OTHER")
        ProjectMember.objects.create(project=other, member=rbac["user"], role=15)
        page = Page.objects.create(workspace=rbac["workspace"], name="Shared", owned_by=rbac["user"])
        for project in (other, rbac["project"]):
            ProjectPage.objects.create(workspace=rbac["workspace"], project=project, page=page)
        role = rbac["role"]
        role.permissions = ["pages.read"]
        role.save()
        base = rbac["base"].replace(str(rbac["project"].id), str(other.id))
        assert rbac["client"].get(base + f"pages/{page.id}/").status_code == 200
        assert rbac["client"].patch(base + f"pages/{page.id}/", {"name": "Bypass"}, format="json").status_code == 403

    def test_workspace_page_asset_without_project_id_is_scoped(self, rbac):
        from types import SimpleNamespace
        from plane.db.models import Page, ProjectPage, FileAsset
        from plane.utils.project_rbac_scope import scoped_queryset

        page = Page.objects.create(workspace=rbac["workspace"], name="Secret page", owned_by=rbac["user"])
        ProjectPage.objects.create(workspace=rbac["workspace"], project=rbac["project"], page=page)
        asset = FileAsset.objects.create(
            workspace=rbac["workspace"], page=page, entity_type="PAGE_DESCRIPTION", asset="secret.png", is_uploaded=True
        )
        assert not scoped_queryset(FileAsset.objects.filter(pk=asset.pk), SimpleNamespace(user=rbac["user"])).exists()
        role = rbac["role"]
        role.permissions = ["pages.read"]
        role.save()
        assert scoped_queryset(FileAsset.objects.filter(pk=asset.pk), SimpleNamespace(user=rbac["user"])).exists()

    def test_analytics_worker_scopes_export_to_authorized_projects(self, rbac, mocker):
        from plane.bgtasks.analytic_plot_export import analytic_export_task

        other = Project.objects.create(workspace=rbac["workspace"], name="Other", identifier="OTHER")
        ProjectMember.objects.create(project=other, member=rbac["user"], role=15)
        Issue.objects.create(project=other, name="Visible", priority="urgent")
        Issue.objects.filter(pk=rbac["issue"].pk).update(priority="high")
        send = mocker.patch("plane.bgtasks.analytic_plot_export.send_export_email")
        analytic_export_task(
            rbac["user"].email, {"x_axis": "priority", "y_axis": "issue_count"}, rbac["workspace"].slug
        )
        send.assert_called_once()
        rows = str(send.call_args.args[3])
        assert "urgent" in rows
        assert "high" not in rows

    @pytest.mark.parametrize("field", ["archived_at", "deleted_at"])
    def test_generic_issue_update_cannot_bypass_lifecycle_permissions(self, rbac, field):
        rbac["role"].permissions = ["issues.read", "issues.update"]
        rbac["role"].save()
        url = rbac["base"] + f"issues/{rbac['issue'].id}/"
        response = rbac["client"].patch(url, {field: timezone.now().isoformat()}, format="json")
        assert response.status_code == 403
        rbac["issue"].refresh_from_db()
        assert getattr(rbac["issue"], field) is None
