# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""THM dashboards: CRUD/permissions, widget data (metrics, grouping,
filters) and viewer-scoped project visibility."""

from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from plane.db.models import (
    Dashboard,
    DashboardWidget,
    Issue,
    IssueAssignee,
    Label,
    IssueLabel,
    Project,
    ProjectMember,
    State,
    User,
    WorkLog,
    WorkspaceMember,
)


def _user(workspace, role, tag):
    suffix = uuid4().hex[:8]
    user = User.objects.create(
        email=f"{tag}-{suffix}@thm.vn", username=f"{tag}-{suffix}", first_name=tag, display_name=tag
    )
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role)
    return user


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _project(workspace, owner, name, ident, members=()):
    project = Project.objects.create(name=name, identifier=ident, workspace=workspace, created_by=owner)
    ProjectMember.objects.create(project=project, member=owner, workspace=workspace, role=20)
    for m in members:
        ProjectMember.objects.create(project=project, member=m, workspace=workspace, role=15)
    states = {}
    for i, (n, g) in enumerate([("Todo", "unstarted"), ("Doing", "started"), ("Done", "completed")]):
        states[n] = State.objects.create(
            name=n, group=g, color="#123", sequence=i * 1000, default=i == 0, project=project, workspace=workspace
        )
    return project, states


def _issue(project, state, owner, name="x", priority="none", assignee=None, label=None, target_date=None):
    issue = Issue(name=name, project=project, workspace=project.workspace, state=state, priority=priority)
    if target_date:
        issue.target_date = target_date
    issue.save(created_by_id=owner.id)
    if assignee:
        IssueAssignee.objects.create(issue=issue, assignee=assignee, project=project, workspace=project.workspace)
    if label:
        IssueLabel.objects.create(issue=issue, label=label, project=project, workspace=project.workspace)
    return issue


@pytest.fixture
def world(db, workspace, create_user):
    """Two projects; `member` is only in project A."""
    member = _user(workspace, 15, "member")
    a, sa = _project(workspace, create_user, "Alpha", f"A{uuid4().hex[:3].upper()}", members=[member])
    b, sb = _project(workspace, create_user, "Beta", f"B{uuid4().hex[:3].upper()}")
    label = Label.objects.create(name="Gấp", color="#f00", project=a, workspace=workspace)
    yesterday = timezone.now().date() - timedelta(days=1)
    i1 = _issue(a, sa["Todo"], create_user, "a1", "high", assignee=member, label=label, target_date=yesterday)
    _issue(a, sa["Doing"], create_user, "a2", "urgent", assignee=member)
    _issue(a, sa["Done"], create_user, "a3", "low")
    _issue(b, sb["Todo"], create_user, "b1", "high")
    _issue(b, sb["Done"], create_user, "b2", "none")
    started = timezone.now() - timedelta(hours=2)
    WorkLog.objects.create(
        issue=i1,
        user=member,
        project=a,
        workspace=workspace,
        duration_seconds=5400,
        started_at=started,
        ended_at=timezone.now(),
        status="approved",
    )
    return {"a": a, "b": b, "sa": sa, "member": member, "admin": create_user, "label": label}


def _base(workspace):
    return f"/api/workspaces/{workspace.slug}/dashboards/"


def _make(client, workspace, name="Tổng quan", **extra):
    r = client.post(_base(workspace), {"name": name, **extra}, format="json")
    assert r.status_code == 201, r.data
    return r.data["id"]


def _widget(client, workspace, did, **payload):
    payload.setdefault("title", "w")
    payload.setdefault("chart_type", "number")
    r = client.post(f"{_base(workspace)}{did}/widgets/", payload, format="json")
    assert r.status_code == 201, r.data
    return r.data["id"]


@pytest.mark.contract
@pytest.mark.django_db
class TestDashboards:
    def test_crud_and_visibility(self, workspace, world):
        admin, member = _client(world["admin"]), _client(world["member"])
        other = _client(_user(workspace, 15, "other"))
        guest = _client(_user(workspace, 5, "guest"))

        shared = _make(member, workspace, "Chung")
        private = _make(member, workspace, "Riêng", is_shared=False)
        assert {d["name"] for d in admin.get(_base(workspace)).data} == {"Chung"}  # admin does not see private
        assert {d["name"] for d in member.get(_base(workspace)).data} == {"Chung", "Riêng"}
        assert guest.get(_base(workspace)).status_code == 200
        assert guest.post(_base(workspace), {"name": "g"}, format="json").status_code == 403

        # edit: owner or workspace admin
        assert other.patch(f"{_base(workspace)}{shared}/", {"name": "x"}, format="json").status_code == 403
        assert admin.patch(f"{_base(workspace)}{shared}/", {"name": "Chung 2"}, format="json").status_code == 200
        assert member.patch(f"{_base(workspace)}{shared}/", {"description": "d"}, format="json").status_code == 200
        assert admin.get(f"{_base(workspace)}{private}/").status_code == 404
        detail = member.get(f"{_base(workspace)}{shared}/").data
        assert detail["can_edit"] is True and detail["widgets"] == []
        assert other.get(f"{_base(workspace)}{shared}/").data["can_edit"] is False

        # widgets: validation + ordering
        w1 = _widget(member, workspace, shared, title="Số lượng")
        r = member.post(f"{_base(workspace)}{shared}/widgets/", {"title": "bad", "chart_type": "bar"}, format="json")
        assert r.status_code == 400 and "group_by" in r.data
        r = member.post(
            f"{_base(workspace)}{shared}/widgets/",
            {"title": "bad", "chart_type": "number", "filters": {"nope": 1}},
            format="json",
        )
        assert r.status_code == 400
        w2 = _widget(member, workspace, shared, title="Theo trạng thái", chart_type="bar", group_by="state")
        assert [w["id"] for w in member.get(f"{_base(workspace)}{shared}/").data["widgets"]] == [w1, w2]
        r = member.post(
            f"{_base(workspace)}{shared}/widgets/reorder/",
            {"widgets": [{"id": w2, "sort_order": 1, "width": 3}, {"id": w1, "sort_order": 2}]},
            format="json",
        )
        assert r.status_code == 200
        widgets = member.get(f"{_base(workspace)}{shared}/").data["widgets"]
        assert [w["id"] for w in widgets] == [w2, w1] and widgets[0]["width"] == 3
        assert other.delete(f"{_base(workspace)}{shared}/widgets/{w1}/").status_code == 403
        assert member.delete(f"{_base(workspace)}{shared}/widgets/{w1}/").status_code == 204
        assert admin.delete(f"{_base(workspace)}{shared}/").status_code == 204
        assert Dashboard.objects.filter(pk=shared).exists() is False

    def test_widget_data_is_scoped_to_viewer_projects(self, workspace, world):
        admin, member = _client(world["admin"]), _client(world["member"])
        did = _make(admin, workspace)
        w = _widget(admin, workspace, did, title="Tất cả")
        url = f"{_base(workspace)}{did}/widgets/{w}/data/"
        assert admin.get(url).data["total"] == 5  # both projects
        assert member.get(url).data["total"] == 3  # only Alpha

        # dashboard pinned to a project
        Dashboard.objects.filter(pk=did).update(project=world["b"])
        assert admin.get(url).data["total"] == 2
        assert member.get(url).data["total"] == 0

    def test_grouping_and_filters(self, workspace, world):
        admin = _client(world["admin"])
        did = _make(admin, workspace)
        base = f"{_base(workspace)}{did}/widgets/"

        def data(**payload):
            wid = _widget(admin, workspace, did, **payload)
            return admin.get(f"{base}{wid}/data/").data

        by_prio = data(chart_type="pie", group_by="priority", filters={"project_ids": [str(world["a"].id)]})
        assert [(g["label"], g["value"]) for g in by_prio["groups"]] == [("Urgent", 1), ("High", 1), ("Low", 1)]
        assert by_prio["groups"][0]["color"] == "#ef4444" and by_prio["total"] == 3

        by_state = data(chart_type="bar", group_by="state", filters={"project_ids": [str(world["a"].id)]})
        assert [g["label"] for g in by_state["groups"]] == ["Todo", "Doing", "Done"]  # state sequence order
        assert by_state["groups"][0]["color"] == "#123"

        by_group = data(chart_type="bar", group_by="state_group")
        assert {g["key"]: g["value"] for g in by_group["groups"]} == {"unstarted": 2, "started": 1, "completed": 2}

        by_project = data(chart_type="bar", group_by="project")
        assert {g["label"]: g["value"] for g in by_project["groups"]} == {"Alpha": 3, "Beta": 2}

        by_assignee = data(chart_type="bar", group_by="assignee")
        assert {g["label"]: g["value"] for g in by_assignee["groups"]} == {"member": 2, "—": 3}

        by_label = data(chart_type="bar", group_by="label", filters={"label_ids": [str(world["label"].id)]})
        assert by_label["groups"] == [{"key": str(world["label"].id), "label": "Gấp", "color": "#f00", "value": 1}]

        overdue = data(filters={"overdue_only": True})
        assert overdue["total"] == 1
        unassigned = data(filters={"unassigned_only": True, "state_groups": ["completed"]})
        assert unassigned["total"] == 2

        by_month = data(chart_type="line", group_by="created_month")
        assert len(by_month["groups"]) == 1 and by_month["groups"][0]["value"] == 5
        assert by_month["groups"][0]["key"] == timezone.now().strftime("%Y-%m")

        this_month = data(filters={"date_range": "this_month", "date_field": "created_at"})
        assert this_month["total"] == 5
        last_month = data(filters={"date_range": "last_month"})
        assert last_month["total"] == 0

        hours = data(metric="worklog_hours")
        assert hours["total"] == 1.5
        hours_by_user = data(metric="worklog_hours", chart_type="bar", group_by="assignee")
        assert hours_by_user["groups"] == [
            {"key": str(world["member"].id), "label": "member", "color": None, "value": 1.5}
        ]

        # one round-trip for everything
        everything = admin.get(f"{_base(workspace)}{did}/data/").data
        assert len(everything) == DashboardWidget.objects.filter(dashboard_id=did).count()
        assert (
            everything[str(DashboardWidget.objects.filter(dashboard_id=did, metric="worklog_hours").first().id)][
                "total"
            ]
            == 1.5
        )

    def test_estimate_points_metric_ignores_non_numeric(self, workspace, world):
        from plane.db.models import Estimate, EstimatePoint

        a = world["a"]
        estimate = Estimate.objects.create(name="Points", project=a, workspace=workspace, type="points")
        p3 = EstimatePoint.objects.create(estimate=estimate, key=0, value="3", project=a, workspace=workspace)
        p5 = EstimatePoint.objects.create(estimate=estimate, key=1, value="5", project=a, workspace=workspace)
        xl = EstimatePoint.objects.create(estimate=estimate, key=2, value="XL", project=a, workspace=workspace)
        issues = list(Issue.objects.filter(project=a).order_by("sequence_id"))
        Issue.objects.filter(pk=issues[0].pk).update(estimate_point=p3)
        Issue.objects.filter(pk=issues[1].pk).update(estimate_point=p5)
        Issue.objects.filter(pk=issues[2].pk).update(estimate_point=xl)

        admin = _client(world["admin"])
        did = _make(admin, workspace)
        wid = _widget(admin, workspace, did, metric="estimate_points", filters={"project_ids": [str(a.id)]})
        assert admin.get(f"{_base(workspace)}{did}/widgets/{wid}/data/").data["total"] == 8
        wid = _widget(admin, workspace, did, metric="estimate_points", chart_type="bar", group_by="state_group")
        groups = {
            g["key"]: g["value"] for g in admin.get(f"{_base(workspace)}{did}/widgets/{wid}/data/").data["groups"]
        }
        assert groups == {"unstarted": 3, "started": 5, "completed": 0}
