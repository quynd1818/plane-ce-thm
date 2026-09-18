# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views.workspace.dashboard import (
    DashboardDataEndpoint,
    DashboardDetailEndpoint,
    DashboardEndpoint,
    DashboardWidgetDataEndpoint,
    DashboardWidgetDetailEndpoint,
    DashboardWidgetEndpoint,
    DashboardWidgetReorderEndpoint,
)

BASE = "workspaces/<str:slug>/dashboards/"

urlpatterns = [
    path(BASE, DashboardEndpoint.as_view(), name="thm-dashboards"),
    path(BASE + "<uuid:dashboard_id>/", DashboardDetailEndpoint.as_view(), name="thm-dashboard-detail"),
    path(BASE + "<uuid:dashboard_id>/data/", DashboardDataEndpoint.as_view(), name="thm-dashboard-data"),
    path(BASE + "<uuid:dashboard_id>/widgets/", DashboardWidgetEndpoint.as_view(), name="thm-dashboard-widgets"),
    path(
        BASE + "<uuid:dashboard_id>/widgets/reorder/",
        DashboardWidgetReorderEndpoint.as_view(),
        name="thm-dashboard-widgets-reorder",
    ),
    path(
        BASE + "<uuid:dashboard_id>/widgets/<uuid:widget_id>/",
        DashboardWidgetDetailEndpoint.as_view(),
        name="thm-dashboard-widget-detail",
    ),
    path(
        BASE + "<uuid:dashboard_id>/widgets/<uuid:widget_id>/data/",
        DashboardWidgetDataEndpoint.as_view(),
        name="thm-dashboard-widget-data",
    ),
]
