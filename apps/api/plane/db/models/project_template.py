# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""THM: project templates.

A template is a workspace-level JSON snapshot of a project's set-up (feature
flags, states, labels, modules, workflow rules and optionally starter work
items). Applying it at project-creation time reproduces that set-up in the
new project. See ``plane.utils.project_template`` for the capture / apply
logic and the exact ``template_data`` schema.
"""

from django.conf import settings
from django.db import models

from .base import BaseModel


class ProjectTemplate(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="project_templates")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    template_data = models.JSONField(default=dict)
    # where the snapshot was taken from (informational only)
    source_project = models.ForeignKey(
        "db.Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="derived_templates"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="project_templates"
    )
    usage_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "project_templates"
        verbose_name = "Project Template"
        verbose_name_plural = "Project Templates"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="project_template_unique_name_workspace_when_deleted_at_null",
            )
        ]

    def __str__(self):
        return f"{self.workspace_id} {self.name}"
