# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""THM: custom dashboards with configurable widgets.

A dashboard belongs to a workspace and holds ordered widgets. Each widget is
a saved query over work items (or worklogs): a metric, an optional grouping
and a set of filters, drawn as a number / bar / pie / line / table. Data is
never stored — it is computed on request by ``plane.utils.dashboard``,
restricted to the projects the *viewer* is a member of.
"""

from django.conf import settings
from django.db import models

from .base import BaseModel


class Dashboard(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="thm_dashboards")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="thm_dashboards"
    )
    # optional default project scope for every widget (widgets may narrow further)
    project = models.ForeignKey(
        "db.Project", on_delete=models.CASCADE, null=True, blank=True, related_name="thm_dashboards"
    )
    is_shared = models.BooleanField(default=True)  # False = only the owner sees it
    logo_props = models.JSONField(default=dict)

    class Meta:
        db_table = "thm_dashboards"
        verbose_name = "Dashboard"
        verbose_name_plural = "Dashboards"
        ordering = ("name",)

    def __str__(self):
        return f"{self.workspace_id} {self.name}"


class DashboardWidget(BaseModel):
    CHART_NUMBER = "number"
    CHART_BAR = "bar"
    CHART_PIE = "pie"
    CHART_LINE = "line"
    CHART_TABLE = "table"
    CHART_CHOICES = (
        (CHART_NUMBER, "Number"),
        (CHART_BAR, "Bar"),
        (CHART_PIE, "Pie"),
        (CHART_LINE, "Line"),
        (CHART_TABLE, "Table"),
    )

    METRIC_COUNT = "count"
    METRIC_ESTIMATE = "estimate_points"
    METRIC_WORKLOG_HOURS = "worklog_hours"
    METRIC_CHOICES = (
        (METRIC_COUNT, "Work item count"),
        (METRIC_ESTIMATE, "Estimate points"),
        (METRIC_WORKLOG_HOURS, "Logged hours"),
    )

    GROUP_CHOICES = (
        ("", "None"),
        ("state", "State"),
        ("state_group", "State group"),
        ("priority", "Priority"),
        ("assignee", "Assignee"),
        ("label", "Label"),
        ("project", "Project"),
        ("module", "Module"),
        ("cycle", "Cycle"),
        ("created_by", "Creator"),
        ("created_month", "Month created"),
        ("completed_month", "Month completed"),
        ("target_month", "Month due"),
    )

    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name="widgets")
    title = models.CharField(max_length=255)
    chart_type = models.CharField(max_length=20, choices=CHART_CHOICES, default=CHART_BAR)
    metric = models.CharField(max_length=30, choices=METRIC_CHOICES, default=METRIC_COUNT)
    group_by = models.CharField(max_length=30, choices=GROUP_CHOICES, blank=True, default="")
    # see plane.utils.dashboard.FILTER_KEYS for the accepted keys
    filters = models.JSONField(default=dict, blank=True)
    # grid: width in columns (1..3 of a 3-column grid), height in rows (1..2)
    width = models.PositiveSmallIntegerField(default=1)
    height = models.PositiveSmallIntegerField(default=1)
    sort_order = models.FloatField(default=65535)
    config = models.JSONField(default=dict, blank=True)  # chart-specific options (limit, show_legend, ...)

    class Meta:
        db_table = "thm_dashboard_widgets"
        verbose_name = "Dashboard Widget"
        verbose_name_plural = "Dashboard Widgets"
        ordering = ("sort_order", "created_at")

    def __str__(self):
        return f"{self.dashboard_id} {self.title}"
