# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""THM workflow & approval: transition rules and their enforcement."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from plane.db.models import Issue, Project, ProjectMember, State, User, WorkflowTransitionRule, WorkspaceMember


def _user(workspace, project, role, tag):
    suffix = uuid4().hex[:8]
    user = User.objects.create(email=f"{tag}-{suffix}@thm.vn", username=f"{tag}-{suffix}", first_name=tag)
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role)
    ProjectMember.objects.create(project=project, member=user, workspace=workspace, role=role)
    return user


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def wf(db, workspace, create_user):
    project = Project.objects.create(
        name="Pháp lý",
        identifier=f"PL{uuid4().hex[:4].upper()}",
        workspace=workspace,
        created_by=create_user,
        is_workflow_enabled=True,
    )
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
    states = {
        name: State.objects.create(name=name, group=group, project=project, workspace=workspace, color="#000", sequence=i)
        for i, (name, group) in enumerate(
            [("Nháp", "backlog"), ("Đang xử lý", "started"), ("Chờ duyệt", "started"), ("Đã duyệt", "completed")]
        )
    }
    issue = Issue(name="Hợp đồng", project=project, workspace=workspace, state=states["Đang xử lý"])
    issue.save(created_by_id=create_user.id)
    member = _user(workspace, project, 15, "member")
    approver = _user(workspace, project, 15, "approver")
    return {"project": project, "states": states, "issue": issue, "admin": create_user, "member": member,
            "approver": approver}


def _patch_state(client, workspace, project, issue, state):
    return client.patch(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/",
        {"state_id": str(state.id)},
        format="json",
    )


@pytest.mark.contract
@pytest.mark.django_db
class TestWorkflowRules:
    def test_no_rules_means_stock_behaviour(self, workspace, wf):
        with patch("plane.notifications.signals.publish_event"):
            r = _patch_state(_client(wf["member"]), workspace, wf["project"], wf["issue"], wf["states"]["Đã duyệt"])
        assert r.status_code in (200, 204), r.data
        wf["issue"].refresh_from_db()
        assert wf["issue"].state_id == wf["states"]["Đã duyệt"].id

    def test_only_admin_can_create_rules(self, workspace, wf):
        url = f"/api/workspaces/{workspace.slug}/projects/{wf['project'].id}/workflow-rules/"
        payload = {"to_state": str(wf["states"]["Đã duyệt"].id), "allowed_roles": [20]}
        assert _client(wf["member"]).post(url, payload, format="json").status_code == 403
        r = _client(wf["admin"]).post(url, payload, format="json")
        assert r.status_code == 201, r.data
        assert r.data["allowed_roles"] == [20]
        # members can still read the rules (the dropdown needs them)
        assert _client(wf["member"]).get(url).status_code == 200

    def test_rule_validation(self, workspace, wf):
        url = f"/api/workspaces/{workspace.slug}/projects/{wf['project'].id}/workflow-rules/"
        admin = _client(wf["admin"])
        done = str(wf["states"]["Đã duyệt"].id)
        assert admin.post(url, {"to_state": done, "allowed_roles": [], "approver_ids": []}, format="json").status_code == 400
        assert admin.post(url, {"to_state": done, "allowed_roles": [99]}, format="json").status_code == 400
        assert admin.post(url, {"to_state": done, "from_state": done, "allowed_roles": [20]}, format="json").status_code == 400
        assert admin.post(url, {"to_state": done, "approver_ids": [str(uuid4())]}, format="json").status_code == 400
        assert admin.post(url, {"to_state": done, "allowed_roles": [20]}, format="json").status_code == 201
        # duplicate transition
        assert admin.post(url, {"to_state": done, "allowed_roles": [15]}, format="json").status_code == 400

    def test_member_blocked_admin_and_approver_allowed(self, workspace, wf):
        WorkflowTransitionRule.objects.create(
            project=wf["project"], workspace=workspace, to_state=wf["states"]["Đã duyệt"],
            allowed_roles=[20], approver_ids=[str(wf["approver"].id)], description="Cần trưởng ban pháp chế duyệt.",
        )
        with patch("plane.notifications.signals.publish_event"):
            r = _patch_state(_client(wf["member"]), workspace, wf["project"], wf["issue"], wf["states"]["Đã duyệt"])
            assert r.status_code == 400, r.data
            assert "Admin" in str(r.data) and "trưởng ban" in str(r.data)
            wf["issue"].refresh_from_db()
            assert wf["issue"].state_id == wf["states"]["Đang xử lý"].id

            # unrelated transitions are still free for the member
            r = _patch_state(_client(wf["member"]), workspace, wf["project"], wf["issue"], wf["states"]["Chờ duyệt"])
            assert r.status_code in (200, 204), r.data

            r = _patch_state(_client(wf["approver"]), workspace, wf["project"], wf["issue"], wf["states"]["Đã duyệt"])
            assert r.status_code in (200, 204), r.data
            wf["issue"].refresh_from_db()
            assert wf["issue"].state_id == wf["states"]["Đã duyệt"].id

    def test_specific_from_state_rule_overrides_wildcard(self, workspace, wf):
        # wildcard: anyone (member) may reach "Đã duyệt"; but from "Nháp" only admin
        WorkflowTransitionRule.objects.create(
            project=wf["project"], workspace=workspace, to_state=wf["states"]["Đã duyệt"], allowed_roles=[20, 15, 5]
        )
        WorkflowTransitionRule.objects.create(
            project=wf["project"], workspace=workspace, from_state=wf["states"]["Nháp"],
            to_state=wf["states"]["Đã duyệt"], allowed_roles=[20],
        )
        with patch("plane.notifications.signals.publish_event"):
            r = _patch_state(_client(wf["member"]), workspace, wf["project"], wf["issue"], wf["states"]["Đã duyệt"])
            assert r.status_code in (200, 204)  # from "Đang xử lý": wildcard applies
            Issue.objects.filter(pk=wf["issue"].pk).update(state=wf["states"]["Nháp"])
            r = _patch_state(_client(wf["member"]), workspace, wf["project"], wf["issue"], wf["states"]["Đã duyệt"])
            assert r.status_code == 400  # from "Nháp": specific rule wins

    def test_feature_flag_off_ignores_rules(self, workspace, wf):
        WorkflowTransitionRule.objects.create(
            project=wf["project"], workspace=workspace, to_state=wf["states"]["Đã duyệt"], allowed_roles=[20]
        )
        Project.objects.filter(pk=wf["project"].pk).update(is_workflow_enabled=False)
        with patch("plane.notifications.signals.publish_event"):
            r = _patch_state(_client(wf["member"]), workspace, wf["project"], wf["issue"], wf["states"]["Đã duyệt"])
        assert r.status_code in (200, 204), r.data

    def test_allowed_states_endpoint(self, workspace, wf):
        WorkflowTransitionRule.objects.create(
            project=wf["project"], workspace=workspace, to_state=wf["states"]["Đã duyệt"], allowed_roles=[20]
        )
        url = (
            f"/api/workspaces/{workspace.slug}/projects/{wf['project'].id}/issues/{wf['issue'].id}/"
            "workflow-allowed-states/"
        )
        r = _client(wf["member"]).get(url)
        assert r.status_code == 200
        by_id = {s["state_id"]: s for s in r.data["states"]}
        assert by_id[str(wf["states"]["Đã duyệt"].id)]["allowed"] is False
        assert by_id[str(wf["states"]["Đã duyệt"].id)]["reason"]
        assert by_id[str(wf["states"]["Chờ duyệt"].id)]["allowed"] is True
        r = _client(wf["admin"]).get(url)
        assert all(s["allowed"] for s in r.data["states"])

    def test_update_and_delete_rule(self, workspace, wf):
        rule = WorkflowTransitionRule.objects.create(
            project=wf["project"], workspace=workspace, to_state=wf["states"]["Đã duyệt"], allowed_roles=[20]
        )
        url = f"/api/workspaces/{workspace.slug}/projects/{wf['project'].id}/workflow-rules/{rule.id}/"
        admin = _client(wf["admin"])
        with patch("plane.notifications.signals.publish_event"):
            r = admin.patch(url, {"allowed_roles": [20, 15]}, format="json")
            assert r.status_code == 200 and r.data["allowed_roles"] == [20, 15]
            assert _client(wf["member"]).delete(url).status_code == 403
            assert admin.delete(url).status_code == 204
        assert not WorkflowTransitionRule.objects.filter(pk=rule.pk).exists()
