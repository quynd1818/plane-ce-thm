# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers.workflow import WorkflowTransitionRuleSerializer
from plane.app.views.base import BaseAPIView
from plane.db.models import Issue, Project, State, WorkflowTransitionRule
from plane.notifications.service import publish_event
from plane.utils.workflow import check_transition


from plane.utils.project_rbac_scope import scoped_queryset


def _rule_payload(project, title):
    return {"title": title, "project_name": project.name}


class WorkflowTransitionRuleEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        rules = WorkflowTransitionRule.objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            project__project_projectmember__member=request.user,
            project__project_projectmember__is_active=True,
        ).distinct()
        return Response(WorkflowTransitionRuleSerializer(rules, many=True).data)

    @allow_permission([ROLE.ADMIN])
    def post(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        serializer = WorkflowTransitionRuleSerializer(data=request.data, context={"project_id": project_id})
        serializer.is_valid(raise_exception=True)
        rule = serializer.save(project=project, workspace=project.workspace)
        publish_event("workflow_rule.changed", _rule_payload(project, "Workflow Rule Created"))
        return Response(WorkflowTransitionRuleSerializer(rule).data, status=status.HTTP_201_CREATED)


class WorkflowTransitionRuleDetailEndpoint(BaseAPIView):
    def get_rule(self, slug, project_id, rule_id):
        return WorkflowTransitionRule.objects.get(pk=rule_id, workspace__slug=slug, project_id=project_id)

    @allow_permission([ROLE.ADMIN])
    def patch(self, request, slug, project_id, rule_id):
        rule = self.get_rule(slug, project_id, rule_id)
        serializer = WorkflowTransitionRuleSerializer(
            rule, data=request.data, partial=True, context={"project_id": project_id}
        )
        serializer.is_valid(raise_exception=True)
        rule = serializer.save()
        publish_event("workflow_rule.changed", _rule_payload(rule.project, "Workflow Rule Updated"))
        return Response(WorkflowTransitionRuleSerializer(rule).data)

    @allow_permission([ROLE.ADMIN])
    def delete(self, request, slug, project_id, rule_id):
        rule = self.get_rule(slug, project_id, rule_id)
        project = rule.project
        rule.delete()
        publish_event("workflow_rule.changed", _rule_payload(project, "Workflow Rule Deleted"))
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkflowAllowedStatesEndpoint(BaseAPIView):
    """States the current user may move a given work item into.

    Used by the state dropdown to grey out transitions before the user tries
    them; the serializer still enforces the rule server-side.
    """

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, issue_id):
        issue = scoped_queryset(Issue.objects.all()).get(pk=issue_id, project_id=project_id, workspace__slug=slug)
        result = []
        for state in State.objects.filter(project_id=project_id).order_by("sequence"):
            decision = check_transition(project_id, request.user, issue.state_id, state.id)
            result.append({"state_id": str(state.id), "allowed": decision.allowed, "reason": decision.reason})
        return Response({"issue_id": str(issue.id), "current_state_id": str(issue.state_id), "states": result})
