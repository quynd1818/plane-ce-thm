# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views.project.workflow import (
    WorkflowAllowedStatesEndpoint,
    WorkflowTransitionRuleDetailEndpoint,
    WorkflowTransitionRuleEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/workflow-rules/",
        WorkflowTransitionRuleEndpoint.as_view(),
        name="workflow-rules",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/workflow-rules/<uuid:rule_id>/",
        WorkflowTransitionRuleDetailEndpoint.as_view(),
        name="workflow-rule-detail",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issues/<uuid:issue_id>/workflow-allowed-states/",
        WorkflowAllowedStatesEndpoint.as_view(),
        name="workflow-allowed-states",
    ),
]
