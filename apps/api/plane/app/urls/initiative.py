# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views.project.epic import (
    ProjectEpicConvertEndpoint,
    ProjectEpicDetailEndpoint,
    ProjectEpicEndpoint,
    ProjectEpicWorkItemsEndpoint,
)
from plane.app.views.workspace.initiative import (
    InitiativeAnalyticsEndpoint,
    InitiativeDetailEndpoint,
    InitiativeEndpoint,
    InitiativeEpicsEndpoint,
    InitiativeProjectsEndpoint,
    WorkspaceEpicEndpoint,
)

P = "workspaces/<str:slug>/projects/<uuid:project_id>/epics/"
INI = "workspaces/<str:slug>/initiatives/"

urlpatterns = [
    # epics
    path(P, ProjectEpicEndpoint.as_view(), name="thm-project-epics"),
    path(P + "convert/", ProjectEpicConvertEndpoint.as_view(), name="thm-project-epic-convert"),
    path(P + "<uuid:epic_id>/", ProjectEpicDetailEndpoint.as_view(), name="thm-project-epic-detail"),
    path(P + "<uuid:epic_id>/work-items/", ProjectEpicWorkItemsEndpoint.as_view(), name="thm-project-epic-work-items"),
    path("workspaces/<str:slug>/epics/", WorkspaceEpicEndpoint.as_view(), name="thm-workspace-epics"),
    # initiatives
    path(INI, InitiativeEndpoint.as_view(), name="thm-initiatives"),
    path(INI + "<uuid:initiative_id>/", InitiativeDetailEndpoint.as_view(), name="thm-initiative-detail"),
    path(INI + "<uuid:initiative_id>/projects/", InitiativeProjectsEndpoint.as_view(), name="thm-initiative-projects"),
    path(INI + "<uuid:initiative_id>/epics/", InitiativeEpicsEndpoint.as_view(), name="thm-initiative-epics"),
    path(
        INI + "<uuid:initiative_id>/analytics/", InitiativeAnalyticsEndpoint.as_view(), name="thm-initiative-analytics"
    ),
]
