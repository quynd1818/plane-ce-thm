# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Evaluate THM workflow transition rules for a state change."""

from dataclasses import dataclass, field

from plane.db.models import Project, ProjectMember, WorkflowTransitionRule

ROLE_LABELS = {20: "Admin", 15: "Member", 5: "Guest"}


@dataclass
class TransitionDecision:
    allowed: bool
    reason: str = ""
    rule_ids: list = field(default_factory=list)


def check_transition(project_id, user, from_state_id, to_state_id) -> TransitionDecision:
    """Return whether ``user`` may move a work item from ``from_state_id`` to ``to_state_id``.

    Allowed when: the project has workflows disabled, the state does not
    change, no active rule targets ``to_state``, or at least one matching rule
    grants it through the user's project role or an explicit approver entry.
    """
    if from_state_id and to_state_id and str(from_state_id) == str(to_state_id):
        return TransitionDecision(True)
    if to_state_id is None:
        return TransitionDecision(True)

    project = Project.objects.filter(pk=project_id).only("id", "is_workflow_enabled").first()
    if project is None or not project.is_workflow_enabled:
        return TransitionDecision(True)

    rules = list(
        WorkflowTransitionRule.objects.filter(project_id=project_id, to_state_id=to_state_id, is_active=True)
        .filter(models_q_from_state(from_state_id))
        .select_related("to_state", "from_state")
    )
    if not rules:
        return TransitionDecision(True)

    # Specific (from_state set) rules take precedence over wildcard rules.
    specific = [rule for rule in rules if rule.from_state_id is not None]
    effective = specific or rules

    membership = (
        ProjectMember.objects.filter(project_id=project_id, member=user, is_active=True).only("role").first()
    )
    role = membership.role if membership else None
    user_id = str(user.id)

    for rule in effective:
        if role is not None and role in (rule.allowed_roles or []):
            return TransitionDecision(True, rule_ids=[str(rule.id)])
        if user_id in [str(uid) for uid in (rule.approver_ids or [])]:
            return TransitionDecision(True, rule_ids=[str(rule.id)])

    rule = effective[0]
    who = ", ".join(ROLE_LABELS.get(r, str(r)) for r in (rule.allowed_roles or []))
    if rule.approver_ids:
        who = f"{who}, named approvers" if who else "named approvers"
    reason = f"Only {who or 'nobody'} can move work items to '{rule.to_state.name}'."
    if rule.description:
        reason = f"{reason} {rule.description}"
    return TransitionDecision(False, reason=reason, rule_ids=[str(r.id) for r in effective])


def models_q_from_state(from_state_id):
    from django.db.models import Q

    if from_state_id is None:
        return Q(from_state__isnull=True)
    return Q(from_state__isnull=True) | Q(from_state_id=from_state_id)
