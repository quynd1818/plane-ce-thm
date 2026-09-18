# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""THM epics.

An epic is a regular work item whose ``type`` is the workspace's epic work
item type (``IssueType.is_epic``). Its children are the work items whose
``parent`` is the epic. Progress is rolled up from the children's state
groups. Nothing here changes how stock endpoints treat those rows, so an
epic still opens in the normal work item detail view.
"""

from django.db.models import Count, Q
from django.utils import timezone

from plane.db.models import Issue, IssueType, ProjectIssueType, ProjectMember

from plane.utils.project_rbac_scope import scoped_queryset


EPIC_TYPE_NAME = "Epic"
STATE_GROUPS = ("backlog", "unstarted", "started", "completed", "cancelled")


def get_or_create_epic_type(workspace, user=None) -> IssueType:
    """One ``is_epic`` type per workspace (reactivated if it was disabled)."""
    epic_type = IssueType.objects.filter(workspace=workspace, is_epic=True).order_by("created_at").first()
    if epic_type is None:
        epic_type = IssueType.objects.create(
            workspace=workspace,
            name=EPIC_TYPE_NAME,
            description="Large body of work that groups related work items.",
            is_epic=True,
            is_active=True,
            logo_props={"in_use": "icon", "icon": {"name": "Layers", "color": "#b91c1c"}},
            created_by=user,
        )
    elif not epic_type.is_active:
        IssueType.objects.filter(pk=epic_type.pk).update(is_active=True)
        epic_type.is_active = True
    return epic_type


def ensure_project_epic_type(project, user=None) -> IssueType:
    epic_type = get_or_create_epic_type(project.workspace, user)
    ProjectIssueType.objects.get_or_create(
        project=project,
        issue_type=epic_type,
        defaults={"workspace": project.workspace, "level": 100, "created_by": user},
    )
    return epic_type


def epic_queryset(workspace_id=None, project_id=None):
    qs = scoped_queryset(Issue.issue_objects.all()).filter(type__is_epic=True)
    if workspace_id:
        qs = qs.filter(workspace_id=workspace_id)
    if project_id:
        qs = qs.filter(project_id=project_id)
    return qs


def visible_issues(qs, user):
    """Apply project membership and restricted guests' creator-only visibility."""
    memberships = ProjectMember.objects.filter(member=user, is_active=True)
    restricted = memberships.filter(role=5, project__guest_view_all_features=False)
    return qs.filter(project_id__in=memberships.values("project_id")).exclude(
        Q(project_id__in=restricted.values("project_id")) & ~Q(created_by=user)
    )


def rollup_for_epics(epic_ids, user) -> dict:
    """``{epic_id: {"total", "backlog", ..., "overdue", "progress"}}`` from the
    epics' direct children."""
    today = timezone.now().date()
    rows = (
        visible_issues(scoped_queryset(Issue.issue_objects.all()).filter(parent_id__in=list(epic_ids)), user)
        .values("parent_id")
        .annotate(
            total=Count("id"),
            **{g: Count("id", filter=Q(state__group=g)) for g in STATE_GROUPS},
            overdue=Count(
                "id",
                filter=Q(target_date__lt=today) & ~Q(state__group__in=["completed", "cancelled"]),
            ),
        )
    )
    out = {str(eid): _empty_rollup() for eid in epic_ids}
    for r in rows:
        total = r["total"]
        done = r["completed"] + r["cancelled"]
        out[str(r["parent_id"])] = {
            "total": total,
            **{g: r[g] for g in STATE_GROUPS},
            "overdue": r["overdue"],
            "progress": round(100 * r["completed"] / (total - r["cancelled"]), 1) if total - r["cancelled"] else 0,
            "done": done,
        }
    return out


def _empty_rollup():
    return {"total": 0, **{g: 0 for g in STATE_GROUPS}, "overdue": 0, "progress": 0, "done": 0}


def rollup_for_queryset(qs) -> dict:
    """Same shape as above for an arbitrary work item queryset (initiatives)."""
    today = timezone.now().date()
    r = qs.aggregate(
        total=Count("id"),
        **{g: Count("id", filter=Q(state__group=g)) for g in STATE_GROUPS},
        overdue=Count("id", filter=Q(target_date__lt=today) & ~Q(state__group__in=["completed", "cancelled"])),
    )
    total = r["total"] or 0
    cancelled = r["cancelled"] or 0
    return {
        "total": total,
        **{g: r[g] or 0 for g in STATE_GROUPS},
        "overdue": r["overdue"] or 0,
        "progress": round(100 * (r["completed"] or 0) / (total - cancelled), 1) if total - cancelled else 0,
        "done": (r["completed"] or 0) + cancelled,
    }
