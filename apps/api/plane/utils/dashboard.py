# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""THM dashboards: turn a widget definition into numbers.

A widget is ``metric`` × ``group_by`` × ``filters``. The queryset is always
restricted to work items in projects the *viewer* is an active member of, so
a shared dashboard never leaks data across projects.

Result shape (same for every chart type)::

    {
      "total": 42,
      "groups": [{"key": "<id or value>", "label": "In progress", "color": "#..", "value": 12}, ...],
      "metric": "count", "group_by": "state"
    }
"""

from datetime import date, timedelta

from django.db.models import Case, Count, F, FloatField, Q, Sum, Value, When
from django.db.models.functions import Cast, Coalesce, TruncMonth
from django.utils import timezone

from plane.db.models import Issue, ProjectMember, WorkLog

FILTER_KEYS = (
    "project_ids",
    "state_ids",
    "state_groups",
    "priorities",
    "assignee_ids",
    "created_by_ids",
    "label_ids",
    "module_ids",
    "cycle_ids",
    "created_after",
    "created_before",
    "target_after",
    "target_before",
    "completed_after",
    "completed_before",
    "date_range",  # this_week | last_week | this_month | last_month | last_30_days | last_90_days | this_year
    "date_field",  # created_at | target_date | completed_at  (what date_range applies to)
    "overdue_only",
    "unassigned_only",
    "include_sub_issues",
)

PRIORITY_COLORS = {
    "urgent": "#ef4444",
    "high": "#f97316",
    "medium": "#eab308",
    "low": "#22c55e",
    "none": "#a3a3a3",
}
STATE_GROUP_COLORS = {
    "backlog": "#a3a3a3",
    "unstarted": "#3b82f6",
    "started": "#f59e0b",
    "completed": "#16a34a",
    "cancelled": "#ef4444",
    "triage": "#8b5cf6",
}
PRIORITY_ORDER = ["urgent", "high", "medium", "low", "none"]
STATE_GROUP_ORDER = ["backlog", "unstarted", "started", "completed", "cancelled", "triage"]
DEFAULT_LIMIT = 12


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _uuid_list(value):
    if not value:
        return []
    if isinstance(value, str):
        value = [v for v in value.split(",") if v]
    return [str(v) for v in value]


def _date_range_bounds(key: str, today: date):
    """Return (start, end) dates for a named range, or (None, None)."""
    if key == "this_week":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    if key == "last_week":
        start = today - timedelta(days=today.weekday() + 7)
        return start, start + timedelta(days=6)
    if key == "this_month":
        return today.replace(day=1), today
    if key == "last_month":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        return last_prev.replace(day=1), last_prev
    if key == "last_30_days":
        return today - timedelta(days=29), today
    if key == "last_90_days":
        return today - timedelta(days=89), today
    if key == "this_year":
        return today.replace(month=1, day=1), today
    return None, None


def visible_project_ids(workspace_id, user) -> list:
    return list(
        ProjectMember.objects.filter(
            workspace_id=workspace_id, member=user, is_active=True, project__archived_at__isnull=True
        ).values_list("project_id", flat=True)
    )


def base_issue_queryset(workspace_id, user, dashboard_project_id, filters: dict):
    """Work items the viewer may see, narrowed by the widget filters."""
    filters = filters or {}
    project_ids = set(str(p) for p in visible_project_ids(workspace_id, user))
    if dashboard_project_id:
        project_ids &= {str(dashboard_project_id)}
    wanted = set(_uuid_list(filters.get("project_ids")))
    if wanted:
        project_ids &= wanted
    if not project_ids:
        return Issue.issue_objects.none()

    qs = Issue.issue_objects.filter(workspace_id=workspace_id, project_id__in=list(project_ids))
    if not filters.get("include_sub_issues", True):
        qs = qs.filter(parent__isnull=True)

    simple = {
        "state_ids": "state_id__in",
        "state_groups": "state__group__in",
        "priorities": "priority__in",
        "assignee_ids": "issue_assignee__assignee_id__in",
        "created_by_ids": "created_by_id__in",
        "label_ids": "label_issue__label_id__in",
        "module_ids": "issue_module__module_id__in",
        "cycle_ids": "issue_cycle__cycle_id__in",
    }
    for key, lookup in simple.items():
        values = _uuid_list(filters.get(key))
        if values:
            qs = qs.filter(**{lookup: values})

    dates = {
        "created_after": "created_at__date__gte",
        "created_before": "created_at__date__lte",
        "target_after": "target_date__gte",
        "target_before": "target_date__lte",
        "completed_after": "completed_at__date__gte",
        "completed_before": "completed_at__date__lte",
    }
    for key, lookup in dates.items():
        if filters.get(key):
            qs = qs.filter(**{lookup: filters[key]})

    start, end = _date_range_bounds(filters.get("date_range") or "", timezone.now().date())
    if start and end:
        field = filters.get("date_field") or "created_at"
        if field == "target_date":
            qs = qs.filter(target_date__gte=start, target_date__lte=end)
        elif field == "completed_at":
            qs = qs.filter(completed_at__date__gte=start, completed_at__date__lte=end)
        else:
            qs = qs.filter(created_at__date__gte=start, created_at__date__lte=end)

    if filters.get("overdue_only"):
        qs = qs.filter(target_date__lt=timezone.now().date()).exclude(state__group__in=["completed", "cancelled"])
    if filters.get("unassigned_only"):
        qs = qs.filter(issue_assignee__isnull=True)
    return qs.distinct()


# --------------------------------------------------------------------------- #
# metric + grouping
# --------------------------------------------------------------------------- #
def _metric_expr(metric: str):
    if metric == "estimate_points":
        # estimate_point.value is a CharField; only numeric values (points) can be summed,
        # categories / t-shirt sizes count as 0 instead of blowing up the cast
        numeric = Case(
            When(estimate_point__value__regex=r"^\d+(\.\d+)?$", then=Cast("estimate_point__value", FloatField())),
            default=Value(0.0),
            output_field=FloatField(),
        )
        return Coalesce(Sum(numeric), Value(0.0))
    return Count("id", distinct=True)


GROUP_FIELDS = {
    "state": ("state_id", "state__name", "state__color", "state__sequence"),
    "state_group": ("state__group", None, None, None),
    "priority": ("priority", None, None, None),
    "assignee": ("issue_assignee__assignee_id", "issue_assignee__assignee__display_name", None, None),
    "label": ("label_issue__label_id", "label_issue__label__name", "label_issue__label__color", None),
    "project": ("project_id", "project__name", None, None),
    "module": ("issue_module__module_id", "issue_module__module__name", None, None),
    "cycle": ("issue_cycle__cycle_id", "issue_cycle__cycle__name", None, None),
    "created_by": ("created_by_id", "created_by__display_name", None, None),
}
MONTH_FIELDS = {
    "created_month": "created_at",
    "completed_month": "completed_at",
    "target_month": "target_date",
}


def _rows_for_worklog_hours(issue_qs, group_by: str, workspace_id):
    """Logged hours are summed on WorkLog, joined through the issue."""
    wl = WorkLog.objects.filter(workspace_id=workspace_id, issue__in=issue_qs.values("id")).exclude(
        is_timer=True, ended_at__isnull=True
    )
    # approval-aware: only approved logs when the project requires approval
    wl = wl.filter(Q(project__is_worklog_approval_enabled=False) | Q(status="approved"))
    hours = Sum(F("duration_seconds")) / Value(3600.0)
    if not group_by:
        total = wl.aggregate(v=hours)["v"] or 0
        return [], round(float(total), 2)
    if group_by in MONTH_FIELDS:
        field = "started_at"
        rows = wl.annotate(bucket=TruncMonth(field)).values("bucket").annotate(value=hours).order_by("bucket")
        return [
            {
                "key": r["bucket"].strftime("%Y-%m") if r["bucket"] else "",
                "label": r["bucket"].strftime("%m/%Y") if r["bucket"] else "—",
                "color": None,
                "value": round(float(r["value"] or 0), 2),
            }
            for r in rows
        ], None
    if group_by == "assignee":
        # hours are attributed to whoever logged them, which is what people expect
        rows = wl.values("user_id", "user__display_name").annotate(value=hours).order_by("-value")
        return [
            {
                "key": str(r["user_id"]),
                "label": r["user__display_name"] or "—",
                "color": None,
                "value": round(float(r["value"] or 0), 2),
            }
            for r in rows
        ], None
    key, label, color, _ = GROUP_FIELDS[group_by]
    prefix = "issue__"
    fields = [prefix + key] + ([prefix + label] if label else []) + ([prefix + color] if color else [])
    rows = wl.values(*fields).annotate(value=hours).order_by("-value")
    out = []
    for r in rows:
        out.append(
            {
                "key": str(r[prefix + key]) if r[prefix + key] is not None else "",
                "label": (r[prefix + label] if label else r[prefix + key]) or "—",
                "color": r[prefix + color] if color else None,
                "value": round(float(r["value"] or 0), 2),
            }
        )
    return out, None


def compute_widget(widget, workspace_id, user) -> dict:
    """Evaluate one widget for ``user``."""
    filters = widget.filters or {}
    group_by = widget.group_by or ""
    metric = widget.metric
    limit = int((widget.config or {}).get("limit") or DEFAULT_LIMIT)
    matched = base_issue_queryset(workspace_id, user, widget.dashboard.project_id, filters)
    # re-select by id so filter joins (assignees, labels, ...) never duplicate rows in the aggregates
    qs = Issue.issue_objects.filter(id__in=matched.values("id"))

    if metric == "worklog_hours":
        groups, total = _rows_for_worklog_hours(qs, group_by, workspace_id)
        if total is None:
            total = round(sum(g["value"] for g in groups), 2)
        groups = _finish_groups(groups, group_by, limit)
        return {"total": total, "groups": groups, "metric": metric, "group_by": group_by}

    expr = _metric_expr(metric)
    if not group_by:
        total = qs.aggregate(v=expr)["v"] or 0
        return {"total": _num(total), "groups": [], "metric": metric, "group_by": group_by}

    if group_by in MONTH_FIELDS:
        field = MONTH_FIELDS[group_by]
        rows = (
            qs.exclude(**{f"{field}__isnull": True})
            .annotate(bucket=TruncMonth(field))
            .values("bucket")
            .annotate(value=expr)
            .order_by("bucket")
        )
        groups = [
            {
                "key": r["bucket"].strftime("%Y-%m"),
                "label": r["bucket"].strftime("%m/%Y"),
                "color": None,
                "value": _num(r["value"]),
            }
            for r in rows
        ]
        total = _num(sum(g["value"] for g in groups))
        return {"total": total, "groups": groups, "metric": metric, "group_by": group_by}

    key, label, color, order = GROUP_FIELDS[group_by]
    fields = [key] + ([label] if label else []) + ([color] if color else []) + ([order] if order else [])
    rows = qs.values(*fields).annotate(value=expr).order_by("-value")
    groups = []
    for r in rows:
        raw_key = r[key]
        groups.append(
            {
                "key": str(raw_key) if raw_key is not None else "",
                "label": (r[label] if label else raw_key) or ("—" if raw_key is None else str(raw_key)),
                "color": r[color] if color else None,
                "value": _num(r["value"]),
                "_order": r[order] if order else None,
            }
        )
    total = _num(qs.aggregate(v=expr)["v"] or 0)
    groups = _finish_groups(groups, group_by, limit)
    return {"total": total, "groups": groups, "metric": metric, "group_by": group_by}


def _finish_groups(groups, group_by, limit):
    """Stable ordering + colors for the enumerated groupings, then cap."""
    if group_by == "priority":
        groups.sort(key=lambda g: PRIORITY_ORDER.index(g["key"]) if g["key"] in PRIORITY_ORDER else 99)
        for g in groups:
            g["color"] = PRIORITY_COLORS.get(g["key"])
            g["label"] = g["key"].capitalize() if g["key"] else "—"
    elif group_by == "state_group":
        groups.sort(key=lambda g: STATE_GROUP_ORDER.index(g["key"]) if g["key"] in STATE_GROUP_ORDER else 99)
        for g in groups:
            g["color"] = STATE_GROUP_COLORS.get(g["key"])
            g["label"] = g["key"].capitalize() if g["key"] else "—"
    elif group_by == "state" and groups and groups[0].get("_order") is not None:
        groups.sort(key=lambda g: g.get("_order") or 0)
    for g in groups:
        g.pop("_order", None)
        if g["label"] == "" or g["label"] is None:
            g["label"] = "—"
    if limit and len(groups) > limit and group_by not in MONTH_FIELDS:
        head, tail = groups[:limit], groups[limit:]
        head.append(
            {"key": "__other__", "label": "Other", "color": "#a3a3a3", "value": _num(sum(g["value"] for g in tail))}
        )
        groups = head
    return groups


def _num(value):
    if value is None:
        return 0
    if isinstance(value, float):
        return int(value) if value.is_integer() else round(value, 2)
    return value
