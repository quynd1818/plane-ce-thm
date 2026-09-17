# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""THM: state-transition rules ("workflow & approval").

A rule restricts who may move a work item INTO ``to_state`` (optionally only
when it currently is in ``from_state``). When no rule matches a transition it
is allowed, so projects without rules behave exactly like stock Plane.
"""

from django.db import models

from .project import ProjectBaseModel


class WorkflowTransitionRule(ProjectBaseModel):
    from_state = models.ForeignKey(
        "db.State",
        on_delete=models.CASCADE,
        related_name="workflow_rules_from",
        null=True,
        blank=True,
        help_text="Only apply when the work item is currently in this state. Empty = any state.",
    )
    to_state = models.ForeignKey("db.State", on_delete=models.CASCADE, related_name="workflow_rules_to")
    # Subset of ROLE_CHOICES values (20 admin, 15 member, 5 guest). Empty list =
    # nobody by role; combine with approver_ids for named approvers.
    allowed_roles = models.JSONField(default=list, blank=True)
    # Explicit user ids that may perform the transition regardless of role.
    approver_ids = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "workflow_transition_rules"
        ordering = ("to_state__sequence", "from_state__sequence", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=["project", "from_state", "to_state"],
                condition=models.Q(deleted_at__isnull=True),
                name="workflow_rule_unique_project_from_to",
            )
        ]

    def __str__(self):
        return f"{self.project_id}: {self.from_state_id or '*'} -> {self.to_state_id}"
