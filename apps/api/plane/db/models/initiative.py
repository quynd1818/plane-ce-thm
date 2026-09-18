# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""THM: initiatives — workspace-level containers that group projects and
epics under one goal, with progress rolled up from their work items.
Epics themselves are plain work items whose ``type`` is the workspace's
``is_epic`` work item type (see ``plane.utils.epic``)."""

from django.conf import settings
from django.db import models

from .base import BaseModel


class Initiative(BaseModel):
    STATUS_CHOICES = (
        ("planned", "Planned"),
        ("in_progress", "In progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="thm_initiatives")
    name = models.CharField(max_length=255)
    description_html = models.TextField(blank=True, default="<p></p>")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")
    lead = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="thm_initiative_leads"
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    logo_props = models.JSONField(default=dict)
    sort_order = models.FloatField(default=65535)
    projects = models.ManyToManyField("db.Project", through="db.InitiativeProject", related_name="thm_initiatives")
    epics = models.ManyToManyField("db.Issue", through="db.InitiativeEpic", related_name="thm_initiatives")

    class Meta:
        db_table = "thm_initiatives"
        verbose_name = "Initiative"
        verbose_name_plural = "Initiatives"
        ordering = ("sort_order", "name")

    def __str__(self):
        return f"{self.workspace_id} {self.name}"


class InitiativeProject(BaseModel):
    initiative = models.ForeignKey(Initiative, on_delete=models.CASCADE, related_name="initiative_projects")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="initiative_links")
    sort_order = models.FloatField(default=65535)

    class Meta:
        db_table = "thm_initiative_projects"
        ordering = ("sort_order",)
        constraints = [
            models.UniqueConstraint(
                fields=["initiative", "project"],
                condition=models.Q(deleted_at__isnull=True),
                name="thm_initiative_project_unique",
            )
        ]


class InitiativeEpic(BaseModel):
    initiative = models.ForeignKey(Initiative, on_delete=models.CASCADE, related_name="initiative_epics")
    epic = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="initiative_links")
    sort_order = models.FloatField(default=65535)

    class Meta:
        db_table = "thm_initiative_epics"
        ordering = ("sort_order",)
        constraints = [
            models.UniqueConstraint(
                fields=["initiative", "epic"],
                condition=models.Q(deleted_at__isnull=True),
                name="thm_initiative_epic_unique",
            )
        ]
