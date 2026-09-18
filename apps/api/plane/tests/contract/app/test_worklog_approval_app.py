# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""THM worklog approval: submitted -> approved/rejected, locks and report totals."""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from plane.db.models import Issue, Project, ProjectMember, User, WorkLog, WorkspaceMember


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
def wl(db, workspace, create_user):
    project = Project.objects.create(
        name="Thi công",
        identifier=f"TC{uuid4().hex[:4].upper()}",
        workspace=workspace,
        created_by=create_user,
        is_time_tracking_enabled=True,
        is_worklog_approval_enabled=True,
    )
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
    issue = Issue(name="Đổ móng", project=project, workspace=workspace)
    issue.save(created_by_id=create_user.id)
    member = _user(workspace, project, 15, "member")
    lead = _user(workspace, project, 15, "lead")  # named approver, not admin
    Project.objects.filter(pk=project.pk).update(worklog_approver_ids=[str(lead.id)])
    project.refresh_from_db()
    return {"project": project, "issue": issue, "admin": create_user, "member": member, "lead": lead}


def _urls(workspace, wl):
    base = f"/api/workspaces/{workspace.slug}/projects/{wl['project'].id}"
    return {
        "logs": f"{base}/issues/{wl['issue'].id}/worklogs/",
        "detail": lambda wid: f"{base}/issues/{wl['issue'].id}/worklogs/{wid}/",
        "review": lambda wid: f"{base}/issues/{wl['issue'].id}/worklogs/{wid}/review/",
        "pending": f"{base}/worklogs/pending/",
        "summary": f"{base}/worklogs/summary/",
        "report": f"{base}/worklogs/report/",
    }


def _log_payload(minutes=30):
    started = timezone.now() - timedelta(minutes=minutes)
    return {"duration_seconds": minutes * 60, "started_at": started.isoformat(), "ended_at": timezone.now().isoformat()}


@pytest.mark.contract
@pytest.mark.django_db
class TestWorklogApproval:
    def test_new_logs_are_submitted_when_approval_enabled(self, workspace, wl):
        u = _urls(workspace, wl)
        with patch("plane.notifications.signals.publish_event"):
            r = _client(wl["member"]).post(u["logs"], _log_payload(), format="json")
        assert r.status_code == 201, r.data
        assert r.data["status"] == "submitted"

        Project.objects.filter(pk=wl["project"].pk).update(is_worklog_approval_enabled=False)
        with patch("plane.notifications.signals.publish_event"):
            r = _client(wl["member"]).post(u["logs"], _log_payload(), format="json")
        assert r.data["status"] == "approved"

    def test_only_approvers_see_queue_and_can_review(self, workspace, wl):
        u = _urls(workspace, wl)
        with patch("plane.notifications.signals.publish_event"):
            wid = _client(wl["member"]).post(u["logs"], _log_payload(), format="json").data["id"]

            assert _client(wl["member"]).get(u["pending"]).status_code == 403
            assert _client(wl["member"]).post(u["review"](wid), {"action": "approve"}, format="json").status_code == 403

            queue = _client(wl["lead"]).get(u["pending"])
            assert queue.status_code == 200 and queue.data["count"] == 1
            assert queue.data["results"][0]["issue_name"] == "Đổ móng"

            # reject needs a note
            r = _client(wl["lead"]).post(u["review"](wid), {"action": "reject"}, format="json")
            assert r.status_code == 400
            r = _client(wl["lead"]).post(u["review"](wid), {"action": "reject", "note": "Thiếu mô tả"}, format="json")
            assert r.status_code == 200 and r.data["status"] == "rejected"
            assert r.data["review_note"] == "Thiếu mô tả" and str(r.data["reviewed_by"]) == str(wl["lead"].id)

            # author fixes it -> back to submitted, note cleared
            r = _client(wl["member"]).patch(u["detail"](wid), {"description": "Đổ móng khu A"}, format="json")
            assert r.status_code == 200 and r.data["status"] == "submitted" and r.data["review_note"] == ""

            # admin approves
            r = _client(wl["admin"]).post(u["review"](wid), {"action": "approve"}, format="json")
            assert r.status_code == 200 and r.data["status"] == "approved"
            assert _client(wl["lead"]).get(u["pending"]).data["count"] == 0

    def test_approved_log_is_locked_for_author_but_not_approver(self, workspace, wl):
        u = _urls(workspace, wl)
        with patch("plane.notifications.signals.publish_event"):
            wid = _client(wl["member"]).post(u["logs"], _log_payload(), format="json").data["id"]
            _client(wl["lead"]).post(u["review"](wid), {"action": "approve"}, format="json")

            r = _client(wl["member"]).patch(u["detail"](wid), {"description": "x"}, format="json")
            assert r.status_code == 403 and "locked" in r.data["error"]
            assert _client(wl["member"]).delete(u["detail"](wid)).status_code == 403

            assert _client(wl["lead"]).patch(u["detail"](wid), {"description": "ok"}, format="json").status_code == 200
            # reopen puts it back in the queue
            r = _client(wl["lead"]).post(u["review"](wid), {"action": "reopen"}, format="json")
            assert r.data["status"] == "submitted" and r.data["reviewed_by"] is None
            assert _client(wl["member"]).patch(u["detail"](wid), {"description": "y"}, format="json").status_code == 200

    def test_reports_count_only_approved_by_default(self, workspace, wl):
        u = _urls(workspace, wl)
        with patch("plane.notifications.signals.publish_event"):
            a = _client(wl["member"]).post(u["logs"], _log_payload(30), format="json").data["id"]
            _client(wl["member"]).post(u["logs"], _log_payload(45), format="json")
            _client(wl["lead"]).post(u["review"](a), {"action": "approve"}, format="json")

        admin = _client(wl["admin"])
        assert admin.get(u["summary"]).data["total_seconds"] == 30 * 60
        assert admin.get(u["summary"], {"status": "all"}).data["total_seconds"] == 75 * 60
        assert admin.get(u["summary"], {"status": "submitted"}).data["total_seconds"] == 45 * 60
        assert admin.get(u["summary"], {"status": "bogus"}).status_code == 400
        assert len(admin.get(u["report"]).data["results"]) == 1

        # approval off -> everything counts again
        Project.objects.filter(pk=wl["project"].pk).update(is_worklog_approval_enabled=False)
        assert admin.get(u["summary"]).data["total_seconds"] == 75 * 60

    def test_running_timer_cannot_be_reviewed(self, workspace, wl):
        u = _urls(workspace, wl)
        base = f"/api/workspaces/{workspace.slug}/projects/{wl['project'].id}/issues/{wl['issue'].id}"
        with patch("plane.notifications.signals.publish_event"):
            wid = _client(wl["member"]).post(f"{base}/timer/").data["id"]
            assert WorkLog.objects.get(pk=wid).status == "submitted"
            assert _client(wl["lead"]).get(u["pending"]).data["count"] == 0  # running timers hidden
            r = _client(wl["lead"]).post(u["review"](wid), {"action": "approve"}, format="json")
            assert r.status_code == 400
            _client(wl["member"]).delete(f"{base}/timer/")
            assert _client(wl["lead"]).get(u["pending"]).data["count"] == 1

    def test_admin_sets_approvers_via_project_patch(self, workspace, wl):
        url = f"/api/workspaces/{workspace.slug}/projects/{wl['project'].id}/"
        r = _client(wl["admin"]).patch(url, {"worklog_approver_ids": [str(wl["member"].id)]}, format="json")
        assert r.status_code == 200, r.data
        assert r.data["worklog_approver_ids"] == [str(wl["member"].id)]
        assert r.data["is_worklog_approval_enabled"] is True
        # the newly named approver can now see the queue; the old one cannot
        assert _client(wl["member"]).get(_urls(workspace, wl)["pending"]).status_code == 200
        assert _client(wl["lead"]).get(_urls(workspace, wl)["pending"]).status_code == 403
