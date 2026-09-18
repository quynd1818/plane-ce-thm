# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views.project.template import (
    ProjectSaveAsTemplateEndpoint,
    ProjectTemplateDetailEndpoint,
    ProjectTemplateEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/project-templates/",
        ProjectTemplateEndpoint.as_view(),
        name="project-templates",
    ),
    path(
        "workspaces/<str:slug>/project-templates/<uuid:template_id>/",
        ProjectTemplateDetailEndpoint.as_view(),
        name="project-template-detail",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/save-as-template/",
        ProjectSaveAsTemplateEndpoint.as_view(),
        name="project-save-as-template",
    ),
]
