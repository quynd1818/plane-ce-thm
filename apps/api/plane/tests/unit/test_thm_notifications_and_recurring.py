# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the THM customisations: Teams notification signals,
recurring issue scheduler and worklog timer behaviour."""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from plane.bgtasks.recurring_issue_task import _advance_past, create_due_recurring_issues
from plane.db.models import (
    Issue,
    IssueAssignee,
    Label,
    Project,
    ProjectMember,
    RecurringIssue,
    State,
    User,
    WorkLog,
    WorkspaceMember,
)


def _events(mock):
    return [call.args[0] for call in mock.call_args_list]


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="THM Project",
        identifier=f"THM{uuid4().hex[:4].upper()}",
        workspace=workspace,
        created_by=create_user,
        is_time_tracking_enabled=True,
    )
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
    return project


@pytest.fixture
def member(db, workspace, project):
    suffix = uuid4().hex[:8]
    user = User.objects.create(email=f"m-{suffix}@plane.so", username=f"m-{suffix}", first_name="Member")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15)
    ProjectMember.objects.create(project=project, member=user, workspace=workspace, role=15)
    return user


@pytest.mark.unit
@pytest.mark.django_db
class TestIssueNotificationSignals:
    def test_created_and_meaningful_update_only(self, project, workspace, create_user):
        with patch("plane.notifications.signals.publish_event") as publish:
            issue = Issue(name="Task", project=project, workspace=workspace)
            issue.save(created_by_id=create_user.id)
            assert _events(publish) == ["issue.created"]

            # noise: sort_order / description changes must NOT notify
            publish.reset_mock()
            issue.sort_order = issue.sort_order + 1
            issue.description_html = "<p>typing…</p>"
            issue.save()
            assert _events(publish) == []

            # meaningful: priority change notifies once
            issue.priority = "high"
            issue.save()
            assert _events(publish) == ["issue.updated"]

    def test_completed_state_emits_completed_not_updated(self, project, workspace, create_user):
        issue = Issue(name="Task", project=project, workspace=workspace)
        issue.save(created_by_id=create_user.id)
        done = State.objects.create(name="Done", group="completed", project=project, workspace=workspace, color="#000")
        with patch("plane.notifications.signals.publish_event") as publish:
            issue.state = done
            issue.save()
            assert _events(publish) == ["issue.completed"]

    def test_soft_delete_emits_deleted_once(self, project, workspace, create_user):
        issue = Issue(name="Task", project=project, workspace=workspace)
        issue.save(created_by_id=create_user.id)
        with patch("plane.notifications.signals.publish_event") as publish:
            issue.delete()  # soft delete -> save() with deleted_at
            assert _events(publish) == ["issue.deleted"]
            publish.reset_mock()
            issue.save()  # re-saving an already deleted issue is silent
            assert _events(publish) == []

    def test_assignment_through_api_notifies_new_assignees_only(self, workspace, project, create_user, member):
        client = APIClient()
        client.force_authenticate(user=create_user)
        url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/"
        with patch("plane.notifications.signals.publish_event") as publish:
            response = client.post(url, {"name": "Assigned", "assignee_ids": [str(member.id)]}, format="json")
            assert response.status_code == 201, response.data
            names = _events(publish)
            assert names.count("issue.assigned") == 1
            assigned_payload = [c.args[1] for c in publish.call_args_list if c.args[0] == "issue.assigned"][0]
            assert assigned_payload["assignee"] == member.display_name

            # re-sending the same assignee list must not re-notify
            publish.reset_mock()
            response = client.patch(
                f"{url}{response.data['id']}/", {"assignee_ids": [str(member.id)]}, format="json"
            )
            assert response.status_code in (200, 204), response.data
            assert "issue.assigned" not in _events(publish)


@pytest.mark.unit
@pytest.mark.django_db
class TestRecurringIssueTask:
    def test_advance_past_skips_missed_periods(self):
        now = timezone.now()
        stale = now - timedelta(days=30)
        nxt = _advance_past(stale, "daily", 1, now)
        assert now < nxt <= now + timedelta(days=1)
        # interval 0 must not loop forever
        assert _advance_past(stale, "weekly", 0, now) > now

    def test_creates_issue_and_drops_stale_assignees_and_labels(self, project, workspace, create_user, member):
        label = Label.objects.create(name="ops", project=project, workspace=workspace)
        gone_user = uuid4()
        gone_label = uuid4()
        recurring = RecurringIssue.objects.create(
            name="Weekly report",
            project=project,
            workspace=workspace,
            frequency="weekly",
            interval=1,
            next_run_at=timezone.now() - timedelta(days=21),
            assignee_ids=[str(member.id), str(gone_user)],
            label_ids=[str(label.id), str(gone_label)],
        )
        with patch("plane.notifications.signals.publish_event"):
            assert create_due_recurring_issues() == 1
            # second tick in the same window creates nothing more
            assert create_due_recurring_issues() == 0

        issue = Issue.objects.get(project=project, name="Weekly report")
        assert set(IssueAssignee.objects.filter(issue=issue).values_list("assignee_id", flat=True)) == {member.id}
        assert list(issue.labels.values_list("id", flat=True)) == [label.id]
        recurring.refresh_from_db()
        assert recurring.next_run_at > timezone.now()
        assert recurring.last_run_at is not None


@pytest.mark.unit
@pytest.mark.django_db
class TestWorklogTimerAndFilters:
    def _issue(self, project, workspace, user):
        issue = Issue(name="Timed", project=project, workspace=workspace)
        issue.save(created_by_id=user.id)
        return issue

    def test_timer_start_stop_computes_duration_and_is_timer_is_read_only(self, workspace, project, member):
        issue = self._issue(project, workspace, member)
        client = APIClient()
        client.force_authenticate(user=member)
        base = f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}"
        with patch("plane.notifications.signals.publish_event"):
            assert client.post(f"{base}/timer/").status_code == 201
            assert client.post(f"{base}/timer/").status_code == 400  # already running
            stopped = client.delete(f"{base}/timer/")
            assert stopped.status_code == 200
            assert stopped.data["ended_at"] is not None
            assert stopped.data["duration_seconds"] >= 1

            # is_timer can no longer be flipped via PATCH
            worklog_id = stopped.data["id"]
            patched = client.patch(f"{base}/worklogs/{worklog_id}/", {"is_timer": False}, format="json")
            assert patched.status_code == 200
            assert WorkLog.objects.get(pk=worklog_id).is_timer is True

    def test_bad_date_filter_returns_400(self, workspace, project, member):
        client = APIClient()
        client.force_authenticate(user=member)
        url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/worklogs/summary/"
        response = client.get(url, {"started_after": "17/09/2026"})
        assert response.status_code == 400
        assert client.get(url, {"started_after": "2026-09-17"}).status_code == 200
