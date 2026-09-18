# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from plane.api.views.issue import IssueDetailAPIEndpoint
from plane.db.models import Issue, Project, ProjectCustomProperty, ProjectMember, State, WorkflowTransitionRule

pytestmark = [pytest.mark.contract, pytest.mark.django_db]


@pytest.fixture
def scenario(workspace, create_user):
    project = Project.objects.create(name="Workflow", identifier="WF", workspace=workspace, is_workflow_enabled=True)
    member = ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=15)
    todo = State.objects.create(name="Todo", group="unstarted", default=True, project=project, workspace=workspace)
    done = State.objects.create(name="Done", group="completed", project=project, workspace=workspace)
    issue = Issue.objects.create(
        name="Existing", project=project, workspace=workspace, state=todo, external_id="1", external_source="test"
    )
    rule = WorkflowTransitionRule.objects.create(
        project=project, workspace=workspace, to_state=done, allowed_roles=[20]
    )
    return project, member, todo, done, issue, rule


@pytest.fixture(autouse=True)
def background_tasks():
    with patch("plane.api.views.issue.issue_activity"), patch("plane.api.views.issue.model_activity"):
        yield


def detail_url(workspace, project, issue):
    return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/"


@pytest.mark.parametrize("method", ["patch", "upsert"])
@pytest.mark.parametrize("access", ["denied", "admin", "approver", "disabled", "no_rule", "unchanged"])
def test_api_state_transition_enforces_workflow(
    api_key_client, api_token, workspace, create_user, scenario, method, access
):
    project, member, todo, done, issue, rule = scenario
    target = done
    if access == "admin":
        member.role = 20
        member.save()
    elif access == "approver":
        rule.approver_ids = [str(create_user.id)]
        rule.save()
    elif access == "disabled":
        project.is_workflow_enabled = False
        project.save()
    elif access == "no_rule":
        rule.delete()
    elif access == "unchanged":
        target = todo
    payload = {"state": str(target.id), "name": "Updated"}
    if method == "patch":
        response = api_key_client.patch(detail_url(workspace, project, issue), payload, format="json")
    else:
        # The upsert handler is not currently exposed by the URL configuration.
        request = APIRequestFactory().put(
            "/",
            {**payload, "external_id": "1", "external_source": "test"},
            format="json",
            HTTP_X_API_KEY=api_token.token,
        )
        response = IssueDetailAPIEndpoint.as_view()(request, slug=workspace.slug, project_id=project.id)
    assert response.status_code == (400 if access == "denied" else 200), response.data
    issue.refresh_from_db()
    if access == "denied":
        assert str(response.data["code"][0]) == "WORKFLOW_TRANSITION_DENIED"
        assert issue.state_id == todo.id and issue.name == "Existing"
    else:
        assert issue.state_id == target.id and issue.name == "Updated"


@pytest.mark.parametrize("retirement", ["deleted", "disabled", "renamed"])
@pytest.mark.parametrize("payload", [{"name": "Updated"}, {"custom_properties": {"active": 2}}])
def test_retired_custom_properties_do_not_block_updates(api_key_client, workspace, scenario, retirement, payload):
    project, _, _, _, issue, _ = scenario
    prop = ProjectCustomProperty.objects.create(project=project, workspace=workspace, name="Old", key="old")
    ProjectCustomProperty.objects.create(
        project=project, workspace=workspace, name="Active", key="active", property_type="number"
    )
    issue.custom_properties = {"old": "historical", "active": 1}
    issue.save()
    if retirement == "deleted":
        prop.deleted_at = timezone.now()
    elif retirement == "disabled":
        prop.is_active = False
    else:
        prop.key = "renamed"
    prop.save()
    response = api_key_client.patch(detail_url(workspace, project, issue), payload, format="json")
    assert response.status_code == 200, response.data
    issue.refresh_from_db()
    assert issue.custom_properties == {"old": "historical", "active": 2 if "custom_properties" in payload else 1}


@pytest.mark.parametrize("properties", [{"unknown": 1}, {"active": "invalid"}])
def test_new_invalid_custom_properties_are_still_rejected(api_key_client, workspace, scenario, properties):
    project, _, _, _, issue, _ = scenario
    ProjectCustomProperty.objects.create(
        project=project, workspace=workspace, name="Active", key="active", property_type="number"
    )
    response = api_key_client.patch(
        detail_url(workspace, project, issue), {"custom_properties": properties}, format="json"
    )
    assert response.status_code == 400, response.data
    issue.refresh_from_db()
    assert issue.custom_properties == {}


@pytest.mark.parametrize("method", ["patch", "upsert"])
def test_null_state_cannot_bypass_protected_default(api_key_client, api_token, workspace, scenario, method):
    project, _, todo, done, issue, _ = scenario
    todo.default = False
    todo.save()
    done.default = True
    done.save()
    if method == "patch":
        response = api_key_client.patch(detail_url(workspace, project, issue), {"state": None}, format="json")
    else:
        request = APIRequestFactory().put(
            "/",
            {"state": None, "external_id": "1", "external_source": "test"},
            format="json",
            HTTP_X_API_KEY=api_token.token,
        )
        response = IssueDetailAPIEndpoint.as_view()(request, slug=workspace.slug, project_id=project.id)
    assert response.status_code == 400, response.data
    issue.refresh_from_db()
    assert issue.state_id == todo.id
