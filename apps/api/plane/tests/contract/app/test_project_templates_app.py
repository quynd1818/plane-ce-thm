# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""THM project templates: save-as-template, CRUD, apply on project create."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from plane.db.models import (
    Issue,
    IssueLabel,
    Label,
    Module,
    ModuleIssue,
    Project,
    ProjectCustomProperty,
    ProjectMember,
    ProjectTemplate,
    State,
    User,
    WorkflowTransitionRule,
    WorkspaceMember,
)


def _user(workspace, role, tag):
    suffix = uuid4().hex[:8]
    user = User.objects.create(email=f"{tag}-{suffix}@thm.vn", username=f"{tag}-{suffix}", first_name=tag)
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role)
    return user


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def source(db, workspace, create_user):
    """A fully set-up project to snapshot: custom states, labels, modules, a
    workflow rule, a custom property and two work items."""
    project = Project.objects.create(
        name="Dự án mẫu",
        identifier=f"DM{uuid4().hex[:4].upper()}",
        workspace=workspace,
        created_by=create_user,
        cycle_view=False,
        module_view=True,
        is_time_tracking_enabled=True,
        is_workflow_enabled=True,
        is_worklog_approval_enabled=True,
    )
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
    names = [("Chuẩn bị", "backlog", True), ("Pháp lý", "started", False), ("Bàn giao", "completed", False)]
    states = {}
    for i, (name, group, default) in enumerate(names):
        states[name] = State.objects.create(
            name=name,
            group=group,
            color="#c00",
            sequence=(i + 1) * 1000,
            default=default,
            project=project,
            workspace=workspace,
        )
    parent = Label.objects.create(name="Khối", color="#111", project=project, workspace=workspace)
    child = Label.objects.create(name="Xây dựng", color="#222", parent=parent, project=project, workspace=workspace)
    module = Module.objects.create(name="Giai đoạn 1", project=project, workspace=workspace, created_by=create_user)
    WorkflowTransitionRule.objects.create(
        from_state=states["Pháp lý"],
        to_state=states["Bàn giao"],
        allowed_roles=[20],
        approver_ids=[str(create_user.id)],
        description="Chỉ admin được bàn giao",
        project=project,
        workspace=workspace,
    )
    ProjectCustomProperty.objects.create(
        name="Chủ đầu tư", key="chu_dau_tu", property_type="text", project=project, workspace=workspace
    )
    for i, name in enumerate(["Xin giấy phép", "Ký hợp đồng"]):
        issue = Issue(name=name, project=project, workspace=workspace, state=states["Pháp lý"], priority="high")
        issue.save(created_by_id=create_user.id)
        if i == 0:
            IssueLabel.objects.create(issue=issue, label=child, project=project, workspace=workspace)
            ModuleIssue.objects.create(issue=issue, module=module, project=project, workspace=workspace)
    return project


def _tpl_urls(workspace):
    return f"/api/workspaces/{workspace.slug}/project-templates/"


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectTemplates:
    def test_save_as_template_captures_structure(self, workspace, create_user, source):
        url = f"/api/workspaces/{workspace.slug}/projects/{source.id}/save-as-template/"
        r = _client(create_user).post(url, {"name": "Mẫu dự án BĐS", "include_work_items": True}, format="json")
        assert r.status_code == 201, r.data
        data = r.data["template_data"]
        assert [s["name"] for s in data["states"]] == ["Chuẩn bị", "Pháp lý", "Bàn giao"]
        assert {lbl["name"]: lbl["parent"] for lbl in data["labels"]} == {"Khối": None, "Xây dựng": "Khối"}
        assert data["modules"][0]["name"] == "Giai đoạn 1"
        rule = data["workflow_rules"][0]
        assert rule == {
            "from_state": "Pháp lý",
            "to_state": "Bàn giao",
            "allowed_roles": [20],
            "description": "Chỉ admin được bàn giao",
        }  # approver_ids (people) are intentionally not captured
        assert data["custom_properties"][0]["key"] == "chu_dau_tu"
        assert data["project"]["is_worklog_approval_enabled"] is True and data["project"]["module_view"] is True
        assert [w["name"] for w in data["work_items"]] == ["Xin giấy phép", "Ký hợp đồng"]
        assert data["work_items"][0]["labels"] == ["Xây dựng"] and data["work_items"][0]["modules"] == ["Giai đoạn 1"]
        assert r.data["summary"]["work_items"] == 2

        # without work items
        r = _client(create_user).post(url, {"name": "Mẫu rỗng"}, format="json")
        assert r.status_code == 201 and r.data["template_data"]["work_items"] == []
        # duplicate name
        assert _client(create_user).post(url, {"name": "Mẫu rỗng"}, format="json").status_code == 409
        # only project admins
        member = _user(workspace, 15, "member")
        ProjectMember.objects.create(project=source, member=member, workspace=workspace, role=15)
        assert _client(member).post(url, {"name": "x"}, format="json").status_code == 403

    def test_apply_template_on_project_create(self, workspace, create_user, source):
        save = f"/api/workspaces/{workspace.slug}/projects/{source.id}/save-as-template/"
        tpl = _client(create_user).post(save, {"name": "Mẫu BĐS", "include_work_items": True}, format="json").data

        with patch("plane.app.views.project.base.model_activity"):
            r = _client(create_user).post(
                f"/api/workspaces/{workspace.slug}/projects/",
                {"name": "Khu đô thị A", "identifier": "KDTA", "template_id": tpl["id"]},
                format="json",
            )
        assert r.status_code == 201, r.data
        project = Project.objects.get(pk=r.data["id"])
        # settings copied, identity not
        assert project.name == "Khu đô thị A" and project.identifier == "KDTA"
        assert project.is_worklog_approval_enabled and project.is_workflow_enabled and project.module_view
        assert project.worklog_approver_ids == []
        # stock default states replaced by the template's
        states = {s.name: s for s in State.objects.filter(project=project)}
        assert set(states) == {"Chuẩn bị", "Pháp lý", "Bàn giao"}
        assert states["Chuẩn bị"].default is True
        # labels keep their hierarchy; modules; rules re-pointed to the new states
        labels = {lbl.name: lbl for lbl in Label.objects.filter(project=project)}
        assert labels["Xây dựng"].parent_id == labels["Khối"].id
        assert Module.objects.filter(project=project, name="Giai đoạn 1").exists()
        rule = WorkflowTransitionRule.objects.get(project=project)
        assert rule.from_state_id == states["Pháp lý"].id and rule.to_state_id == states["Bàn giao"].id
        assert rule.allowed_roles == [20] and rule.approver_ids == []
        assert ProjectCustomProperty.objects.filter(project=project, key="chu_dau_tu").exists()
        # starter work items with sequence ids, labels and modules
        issues = list(Issue.objects.filter(project=project).order_by("sequence_id"))
        assert [i.name for i in issues] == ["Xin giấy phép", "Ký hợp đồng"]
        assert [i.sequence_id for i in issues] == [1, 2]
        assert issues[0].state_id == states["Pháp lý"].id and issues[0].priority == "high"
        assert IssueLabel.objects.filter(issue=issues[0], label=labels["Xây dựng"]).exists()
        assert ModuleIssue.objects.filter(issue=issues[0], module__name="Giai đoạn 1").exists()
        # source project untouched, usage counted
        assert Issue.objects.filter(project=source).count() == 2
        assert ProjectTemplate.objects.get(pk=tpl["id"]).usage_count == 1

        # unknown template -> 400, project not created
        with patch("plane.app.views.project.base.model_activity"):
            r = _client(create_user).post(
                f"/api/workspaces/{workspace.slug}/projects/",
                {"name": "Khu B", "identifier": "KHUB", "template_id": str(uuid4())},
                format="json",
            )
        assert r.status_code == 400 and not Project.objects.filter(identifier="KHUB").exists()

    def test_template_crud_and_permissions(self, workspace, create_user):
        admin = _client(create_user)
        member = _user(workspace, 15, "member")
        guest = _user(workspace, 5, "guest")
        url = _tpl_urls(workspace)

        # member creates a raw template (validated)
        r = _client(member).post(url, {"name": "Thô", "template_data": {"states": [{"color": "#000"}]}}, format="json")
        assert r.status_code == 400
        r = _client(member).post(
            url,
            {"name": "Thô", "template_data": {"project": {"cycle_view": True}, "states": [{"name": "Mới"}]}},
            format="json",
        )
        assert r.status_code == 201 and r.data["summary"]["states"] == 1
        tid = r.data["id"]
        # unknown project setting is rejected
        r = _client(member).post(url, {"name": "Xấu", "template_data": {"project": {"identifier": "X"}}}, format="json")
        assert r.status_code == 400

        # everyone in the workspace can list; lite listing has no payload
        assert _client(guest).get(url).status_code == 200
        lite = _client(guest).get(url, {"lite": "true"}).data
        assert lite[0]["name"] == "Thô" and "template_data" not in lite[0]
        assert _client(guest).post(url, {"name": "G"}, format="json").status_code == 403

        # only owner or workspace admin can edit / delete
        other = _user(workspace, 15, "other")
        assert _client(other).patch(f"{url}{tid}/", {"name": "Đổi"}, format="json").status_code == 403
        assert _client(member).patch(f"{url}{tid}/", {"name": "Đổi"}, format="json").status_code == 200
        assert admin.patch(f"{url}{tid}/", {"description": "ok"}, format="json").status_code == 200
        assert _client(other).delete(f"{url}{tid}/").status_code == 403
        assert admin.delete(f"{url}{tid}/").status_code == 204
        assert admin.get(f"{url}{tid}/").status_code == 404

    def test_applying_minimal_template_keeps_default_states(self, workspace, create_user):
        tpl = ProjectTemplate.objects.create(
            workspace=workspace, name="Chỉ nhãn", template_data={"labels": [{"name": "Gấp"}]}, owner=create_user
        )
        with patch("plane.app.views.project.base.model_activity"):
            r = _client(create_user).post(
                f"/api/workspaces/{workspace.slug}/projects/",
                {"name": "Tối giản", "identifier": "TGN", "template_id": str(tpl.id)},
                format="json",
            )
        assert r.status_code == 201, r.data
        assert State.objects.filter(project_id=r.data["id"]).count() == 5  # stock defaults kept
        assert Label.objects.filter(project_id=r.data["id"], name="Gấp").exists()


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("legacy", [False, True])
def test_work_item_template_defaults_remap_to_destination(workspace, create_user, source, legacy):
    from copy import deepcopy

    from plane.app.serializers import IssueCreateSerializer
    from plane.db.models import WorkItemTemplate
    from plane.utils.project_template import capture_project

    source_state = State.objects.get(project=source, name="Pháp lý")
    source_label = Label.objects.get(project=source, name="Xây dựng")
    source_module = Module.objects.get(project=source, name="Giai đoạn 1")
    defaults = {
        "name": "From template",
        "description_html": "<p>Details</p>",
        "priority": "high",
        "state_id": str(source_state.id),
        "label_ids": [str(source_label.id)],
        "module_ids": [str(source_module.id)],
        "assignee_ids": [str(create_user.id)],
        "project_id": str(source.id),
        "workspace_id": str(workspace.id),
        "parent_id": str(uuid4()),
        "cycle_id": str(uuid4()),
        "type_id": str(uuid4()),
        "custom_properties": {"chu_dau_tu": "THM"},
    }
    original = WorkItemTemplate.objects.create(project=source, workspace=workspace, name="Task", defaults=defaults)
    snapshot = capture_project(source)
    portable = snapshot["work_item_templates"][0]["defaults"]
    assert portable == {
        "name": "From template",
        "description_html": "<p>Details</p>",
        "priority": "high",
        "state": "Pháp lý",
        "labels": ["Xây dựng"],
        "modules": ["Giai đoạn 1"],
        "custom_properties": {"chu_dau_tu": "THM"},
    }
    if legacy:
        snapshot["work_item_templates"][0]["defaults"] = defaults
    else:
        # A portable snapshot must not depend on the source still having these names.
        source_state.name = "Renamed after snapshot"
        source_state.save()
    before = deepcopy(snapshot)
    template = ProjectTemplate.objects.create(
        workspace=workspace, owner=create_user, source_project=source, name="Portable", template_data=snapshot
    )
    with patch("plane.app.views.project.base.model_activity"):
        response = _client(create_user).post(
            f"/api/workspaces/{workspace.slug}/projects/",
            {"name": "Destination", "identifier": "DEST", "template_id": str(template.id)},
            format="json",
        )
    assert response.status_code == 201, response.data
    destination = Project.objects.get(pk=response.data["id"])
    copied = WorkItemTemplate.objects.get(project=destination)
    expected = {
        "name": "From template",
        "description_html": "<p>Details</p>",
        "priority": "high",
        "state_id": str(State.objects.get(project=destination, name="Pháp lý").id),
        "label_ids": [str(Label.objects.get(project=destination, name="Xây dựng").id)],
        "module_ids": [str(Module.objects.get(project=destination, name="Giai đoạn 1").id)],
        "custom_properties": {"chu_dau_tu": "THM"},
    }
    assert copied.defaults == expected
    serializer = IssueCreateSerializer(
        data=copied.defaults,
        context={"project_id": destination.id, "workspace_id": workspace.id, "default_assignee_id": None},
    )
    assert serializer.is_valid(), serializer.errors
    issue = serializer.save()
    assert str(issue.state_id) == expected["state_id"]
    assert list(issue.labels.values_list("id", flat=True)) == [
        Label.objects.get(project=destination, name="Xây dựng").id
    ]
    original.refresh_from_db()
    template.refresh_from_db()
    assert original.defaults == defaults and template.template_data == before


@pytest.mark.unit
@pytest.mark.django_db
def test_legacy_defaults_without_source_drop_foreign_ids(workspace, create_user):
    from plane.db.models import WorkItemTemplate
    from plane.utils.project_template import apply_template

    project = Project.objects.create(workspace=workspace, name="Orphan snapshot", identifier="ORPH")
    apply_template(
        project,
        {
            "work_item_templates": [
                {
                    "name": "Task",
                    "defaults": {
                        "name": "Safe",
                        "state_id": str(uuid4()),
                        "label_ids": [str(uuid4())],
                        "assignee_ids": [str(create_user.id)],
                    },
                }
            ]
        },
        create_user,
    )
    assert WorkItemTemplate.objects.get(project=project).defaults == {"name": "Safe"}
