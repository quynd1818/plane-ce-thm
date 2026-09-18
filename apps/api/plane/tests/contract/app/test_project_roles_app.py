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
    role.permissions = ["issues.read", "properties.edit"]
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
        for role in (5, 20):
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
            {"name": "Invalid", "permissions": ["issues.read", "properties.edit"], "property_keys": ["other"]},
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
            f"/api/workspaces/{slug}/export-issues/", {"project": [str(rbac["project"].id)]}, format="json"
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

    def test_unassigned_project_cannot_be_used_as_cross_project_bypass(self, rbac):
        other = Project.objects.create(workspace=rbac["workspace"], name="Other", identifier="OTHER")
        ProjectMember.objects.create(project=other, member=rbac["user"], role=20)
        base = rbac["base"].replace(str(rbac["project"].id), str(other.id))
        assert rbac["client"].get(base + "issues/").status_code == 403
        assert rbac["client"].get(base + "worklogs/report/").status_code == 403

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
                "permissions": ["issues.read", "properties.edit"],
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
