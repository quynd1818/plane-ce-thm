# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""THM epics (project) and initiatives (workspace)."""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from plane.db.models import (
    Initiative,
    Issue,
    IssueType,
    Project,
    ProjectIssueType,
    ProjectMember,
    State,
    User,
    WorkspaceMember,
)


def _user(workspace, role, tag):
    suffix = uuid4().hex[:8]
    user = User.objects.create(email=f"{tag}-{suffix}@thm.vn", username=f"{tag}-{suffix}", display_name=tag)
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role)
    return user


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _project(workspace, owner, name, ident, members=(), epics=True):
    project = Project.objects.create(
        name=name, identifier=ident, workspace=workspace, created_by=owner, is_epic_enabled=epics
    )
    ProjectMember.objects.create(project=project, member=owner, workspace=workspace, role=20)
    for m in members:
        ProjectMember.objects.create(project=project, member=m, workspace=workspace, role=15)
    states = {}
    for i, (n, g) in enumerate(
        [("Todo", "unstarted"), ("Doing", "started"), ("Done", "completed"), ("Drop", "cancelled")]
    ):
        states[n] = State.objects.create(
            name=n, group=g, color="#123", sequence=i * 1000, default=i == 0, project=project, workspace=workspace
        )
    return project, states


def _issue(project, state, owner, name="x", **kw):
    issue = Issue(name=name, project=project, workspace=project.workspace, state=state, **kw)
    issue.save(created_by_id=owner.id)
    return issue


@pytest.fixture
def world(db, workspace, create_user):
    member = _user(workspace, 15, "member")
    a, sa = _project(workspace, create_user, "Alpha", f"A{uuid4().hex[:3].upper()}", members=[member])
    b, sb = _project(workspace, create_user, "Beta", f"B{uuid4().hex[:3].upper()}")
    return {"a": a, "sa": sa, "b": b, "sb": sb, "admin": create_user, "member": member}


def _epics(workspace, project):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}/epics/"


@pytest.mark.contract
@pytest.mark.django_db
class TestEpics:
    def test_create_epic_attach_children_and_rollup(self, workspace, world):
        a, sa, admin = world["a"], world["sa"], _client(world["admin"])
        with patch("plane.app.views.project.epic.issue_activity"):
            r = admin.post(_epics(workspace, a), {"name": "Khu A", "priority": "high"}, format="json")
        assert r.status_code == 201, r.data
        epic_id = r.data["id"]
        assert r.data["rollup"]["total"] == 0 and r.data["sequence_id"] == 1
        # a workspace epic type was created lazily and linked to the project
        epic_type = IssueType.objects.get(workspace=workspace, is_epic=True)
        assert Issue.objects.get(pk=epic_id).type_id == epic_type.id
        assert ProjectIssueType.objects.filter(project=a, issue_type=epic_type).exists()

        # children: 1 todo, 1 doing, 1 done, 1 cancelled, one overdue
        yesterday = timezone.now().date() - timedelta(days=1)
        kids = [
            _issue(a, sa["Todo"], world["admin"], "k1", target_date=yesterday),
            _issue(a, sa["Doing"], world["admin"], "k2"),
            _issue(a, sa["Done"], world["admin"], "k3"),
            _issue(a, sa["Drop"], world["admin"], "k4"),
        ]
        other_project_issue = _issue(world["b"], world["sb"]["Todo"], world["admin"], "b1")
        url = f"{_epics(workspace, a)}{epic_id}/work-items/"
        r = admin.post(url, {"issue_ids": [str(k.id) for k in kids]}, format="json")
        assert r.status_code == 200, r.data
        assert r.data["rollup"] == {
            "total": 4,
            "backlog": 0,
            "unstarted": 1,
            "started": 1,
            "completed": 1,
            "cancelled": 1,
            "overdue": 1,
            "progress": 33.3,
            "done": 2,
        }
        assert Issue.objects.get(pk=kids[0].pk).parent_id == uuid_(epic_id)
        # cross-project or epic-in-epic attach is refused
        assert admin.post(url, {"issue_ids": [str(other_project_issue.id)]}, format="json").status_code == 400
        assert admin.post(url, {"issue_ids": [epic_id]}, format="json").status_code == 400

        # list + detail
        rows = admin.get(_epics(workspace, a)).data
        assert [x["id"] for x in rows] == [epic_id] and rows[0]["rollup"]["total"] == 4
        detail = admin.get(f"{_epics(workspace, a)}{epic_id}/").data
        assert [w["name"] for w in detail["work_items"]] == ["k1", "k2", "k3", "k4"]
        # epics are not listed as regular children of anything; epic still opens as a work item
        assert admin.get(f"/api/workspaces/{workspace.slug}/projects/{a.id}/issues/{epic_id}/").status_code == 200

        # detach one, then demote the epic: children are released, work item survives
        r = admin.delete(url, {"issue_ids": [str(kids[3].id)]}, format="json")
        assert r.data["rollup"]["total"] == 3
        assert admin.delete(f"{_epics(workspace, a)}{epic_id}/").status_code == 204
        assert Issue.objects.get(pk=epic_id).type_id is None
        assert Issue.objects.filter(parent_id=epic_id).count() == 0
        assert admin.get(_epics(workspace, a)).data == []

    def test_convert_and_permissions(self, workspace, world):
        a, sa = world["a"], world["sa"]
        admin, member = _client(world["admin"]), _client(world["member"])
        guest = _user(workspace, 5, "guest")
        ProjectMember.objects.create(project=a, member=guest, workspace=workspace, role=5)

        parent = _issue(a, sa["Todo"], world["admin"], "P")
        child = _issue(a, sa["Todo"], world["admin"], "C", parent=parent)
        url = f"{_epics(workspace, a)}convert/"
        # a child cannot become an epic
        assert member.post(url, {"issue_id": str(child.id)}, format="json").status_code == 400
        r = member.post(url, {"issue_id": str(parent.id)}, format="json")
        assert r.status_code == 200 and r.data["rollup"]["total"] == 1
        assert _client(guest).post(url, {"issue_id": str(parent.id)}, format="json").status_code == 403
        assert _client(guest).get(_epics(workspace, a)).status_code == 200

        # feature toggle off -> no new epics
        Project.objects.filter(pk=a.pk).update(is_epic_enabled=False)
        with patch("plane.app.views.project.epic.issue_activity"):
            assert admin.post(_epics(workspace, a), {"name": "x"}, format="json").status_code == 400

        # workspace-wide epic list is scoped to the viewer's projects
        _issue(
            world["b"],
            world["sb"]["Todo"],
            world["admin"],
            "BE",
            type=IssueType.objects.get(is_epic=True, workspace=workspace),
        )
        ws = f"/api/workspaces/{workspace.slug}/epics/"
        assert {e["name"] for e in admin.get(ws).data} == {"P", "BE"}
        assert {e["name"] for e in member.get(ws).data} == {"P"}
        assert [e["name"] for e in admin.get(ws, {"project_id": str(world["b"].id)}).data] == ["BE"]


def uuid_(value):
    from uuid import UUID

    return UUID(str(value))


@pytest.mark.contract
@pytest.mark.django_db
class TestInitiatives:
    def test_crud_links_and_rollup(self, workspace, world):
        a, sa, b, sb = world["a"], world["sa"], world["b"], world["sb"]
        admin, member = _client(world["admin"]), _client(world["member"])
        base = f"/api/workspaces/{workspace.slug}/initiatives/"

        r = member.post(
            base,
            {"name": "Chuyển đổi số", "status": "in_progress", "start_date": "2026-01-01", "end_date": "2025-01-01"},
            format="json",
        )
        assert r.status_code == 400
        r = member.post(
            base, {"name": "Chuyển đổi số", "status": "in_progress", "lead": str(world["member"].id)}, format="json"
        )
        assert r.status_code == 201, r.data
        iid = r.data["id"]
        assert r.data["project_ids"] == [] and r.data["lead_detail"]["display_name"] == "member"

        # link projects (member may: they created it)
        r = member.post(f"{base}{iid}/projects/", {"project_ids": [str(a.id), str(b.id)]}, format="json")
        assert r.status_code == 200 and set(r.data["project_ids"]) == {str(a.id), str(b.id)}
        assert member.post(f"{base}{iid}/projects/", {"project_ids": [str(uuid4())]}, format="json").status_code == 400

        # work in the projects
        _issue(a, sa["Done"], world["admin"], "a-done")
        _issue(a, sa["Todo"], world["admin"], "a-todo")
        _issue(b, sb["Done"], world["admin"], "b-done")
        # an epic in Beta with one child, linked directly (also counted through the project)
        epic = _issue(
            b,
            sb["Todo"],
            world["admin"],
            "BE",
            type=IssueType.objects.create(workspace=workspace, name="Epic", is_epic=True),
        )
        _issue(b, sb["Doing"], world["admin"], "b-kid", parent=epic)
        r = member.post(f"{base}{iid}/epics/", {"epic_ids": [str(epic.id)]}, format="json")
        assert r.status_code == 200 and r.data["epic_ids"] == [str(epic.id)]
        assert member.post(f"{base}{iid}/epics/", {"epic_ids": [str(uuid4())]}, format="json").status_code == 400

        # admin sees both projects: 4 work items (epic itself excluded), 2 done, 1 doing
        an = admin.get(f"{base}{iid}/analytics/").data
        assert (an["total"], an["completed"], an["started"], an["project_count"], an["epic_count"]) == (4, 2, 1, 2, 1)
        assert an["progress"] == 50
        # member is only in Alpha: 2 items, and Beta's epic child is invisible to them
        an = member.get(f"{base}{iid}/analytics/").data
        assert (an["total"], an["completed"], an["project_count"]) == (2, 1, 1)

        detail = member.get(f"{base}{iid}/").data
        assert detail["can_edit"] is True
        assert {p["identifier"]: p["is_member"] for p in detail["projects"]} == {
            a.identifier: True,
            b.identifier: False,
        }
        assert detail["epics"] == []  # Beta epic not visible to member
        assert [e["name"] for e in admin.get(f"{base}{iid}/").data["epics"]] == ["BE"]

        # list with analytics
        rows = admin.get(base, {"analytics": "true"}).data
        assert rows[0]["analytics"]["total"] == 4

        # permissions: another member cannot edit, admin can
        other = _client(_user(workspace, 15, "other"))
        assert other.patch(f"{base}{iid}/", {"name": "x"}, format="json").status_code == 403
        assert other.get(f"{base}{iid}/").data["can_edit"] is False
        assert admin.patch(f"{base}{iid}/", {"status": "completed"}, format="json").data["status"] == "completed"
        assert _client(_user(workspace, 5, "guest")).post(base, {"name": "g"}, format="json").status_code == 403

        # unlink + delete
        r = member.delete(f"{base}{iid}/projects/", {"project_ids": [str(b.id)]}, format="json")
        assert r.data["project_ids"] == [str(a.id)]
        assert other.delete(f"{base}{iid}/").status_code == 403
        assert member.delete(f"{base}{iid}/").status_code == 204
        assert not Initiative.objects.filter(pk=iid).exists()
