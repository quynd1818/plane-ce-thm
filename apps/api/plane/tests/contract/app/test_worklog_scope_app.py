# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Issue, Project, ProjectMember, User, WorkLog, WorkspaceMember


def _make_issue(name, project, workspace, author):
    issue = Issue(name=name, project=project, workspace=workspace)
    issue.save(created_by_id=author.id)
    return issue


def _worklog_url(workspace, project, issue, worklog=None):
    url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/worklogs/"
    return f"{url}{worklog.id}/" if worklog else url


@pytest.fixture
def worklog_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Worklog Project",
        identifier=f"WL{uuid4().hex[:4].upper()}",
        workspace=workspace,
        created_by=create_user,
        is_time_tracking_enabled=True,
    )
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
    issue = _make_issue("Tracked issue", project, workspace, create_user)
    return project, issue


@pytest.fixture
def worklog_member(db, workspace, worklog_project):
    project, _ = worklog_project
    member = User.objects.create(email=f"worklog-{uuid4().hex[:8]}@plane.so", first_name="Worklog")
    WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
    ProjectMember.objects.create(project=project, member=member, workspace=workspace, role=15)
    return member


@pytest.mark.contract
@pytest.mark.django_db
class TestWorklogScope:
    def test_member_can_create_and_update_own_worklog(self, workspace, worklog_project, worklog_member):
        project, issue = worklog_project
        client = APIClient()
        client.force_authenticate(user=worklog_member)
        started_at = timezone.now() - timedelta(minutes=30)
        response = client.post(
            _worklog_url(workspace, project, issue),
            {
                "duration_seconds": 1800,
                "started_at": started_at.isoformat(),
                "ended_at": timezone.now().isoformat(),
                "description": "Initial entry",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        worklog = WorkLog.objects.get(id=response.data["id"])
        response = client.patch(
            _worklog_url(workspace, project, issue, worklog),
            {"description": "Updated entry", "issue": str(uuid4())},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        worklog.refresh_from_db()
        assert worklog.description == "Updated entry"
        assert worklog.issue_id == issue.id

    def test_inactive_member_cannot_read_project_worklogs(self, workspace, worklog_project, worklog_member):
        project, issue = worklog_project
        ProjectMember.objects.filter(project=project, member=worklog_member).update(is_active=False)
        client = APIClient()
        client.force_authenticate(user=worklog_member)

        response = client.get(_worklog_url(workspace, project, issue))

        assert response.status_code == status.HTTP_403_FORBIDDEN

