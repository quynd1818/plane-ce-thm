"""Explicit row scopes shared by project and workspace queries.

This never grants access: existing membership/privacy filters still apply. All
queries, including counts/subqueries, are filtered before pagination/aggregation.
"""

from contextvars import ContextVar
from django.db.models import Q
from rest_framework import serializers

current_role_request = ContextVar("current_role_request", default=None)

# Model -> (capability, project lookup). Related rows may require both projects.
MODEL_SCOPES = {
    "Issue": (("issues.read", "project_id"),),
    "UserFavorite": (),
    "UserRecentVisit": (),
    "ExporterHistory": (),
    "IssueActivity": (("issues.read", "project_id"),),
    "IssueVersion": (("issues.read", "project_id"),),
    "IssueDescriptionVersion": (("issues.read", "project_id"),),
    "IssueComment": (("issues.read", "project_id"), ("comments.read", "project_id")),
    "IssueRelation": (("issues.read", "issue__project_id"), ("issues.read", "related_issue__project_id")),
    "IssueLink": (("issues.read", "project_id"),),
    "IssueAssignee": (("issues.read", "project_id"),),
    "IssueLabel": (("issues.read", "project_id"),),
    "IssueSubscriber": (("issues.read", "project_id"),),
    "IssueReaction": (("issues.read", "project_id"),),
    "CommentReaction": (("issues.read", "project_id"),),
    "IssueAttachment": (("attachments.read", "project_id"),),
    "Cycle": (("cycles.read", "project_id"),),
    "CycleIssue": (("cycles.read", "project_id"), ("issues.read", "issue__project_id")),
    "Module": (("modules.read", "project_id"),),
    "ModuleIssue": (("modules.read", "project_id"), ("issues.read", "issue__project_id")),
    "ModuleLink": (("modules.read", "project_id"),),
    "Page": (("pages.read", "projects__id"),),
    "PageVersion": (("pages.read", "page__projects__id"),),
    "ProjectPage": (("pages.read", "project_id"),),
    "IssueView": (("views.read", "project_id"),),
    "Intake": (("intake.read", "project_id"),),
    "IntakeIssue": (("intake.read", "project_id"),),
    "DraftIssue": (("issues.read", "project_id"),),
    "WorkLog": (("worklogs.read", "project_id"),),
    "Notification": (("issues.read", "project_id"),),
    "FileAsset": (("attachments.read", "project_id"),),
    "RecurringIssue": (("automation.read", "project_id"),),
    "IntakeForm": (("intake.read", "project_id"),),
    "Dashboard": (("analytics.read", "project_id"),),
    "InitiativeProject": (("issues.read", "project_id"),),
    "InitiativeEpic": (("issues.read", "epic__project_id"),),
}


def scoped_queryset(queryset, request_or_user=None, capability=None, project_field=None):
    from plane.utils.project_rbac import role_assignments, assignment_allows

    request_or_user = request_or_user or current_role_request.get()
    if request_or_user is None:
        return queryset
    scopes = MODEL_SCOPES.get(queryset.model.__name__, ())
    if capability:
        scopes = ((capability, project_field or "project_id"),)
    if getattr(request_or_user, "rbac_capability", None) in (
        "analytics.read",
        "analytics.export",
    ) and queryset.model.__name__ in ("Issue", "WorkLog"):
        scopes = (*scopes, ("analytics.read", "project_id"))
    assignments = role_assignments(request_or_user)
    if not assignments:
        return queryset
    model_name = queryset.model.__name__
    if model_name == "ExporterHistory":
        denied = [a.project_id for a in assignments if not assignment_allows(a, "issues.export")]
        return queryset.exclude(project__overlap=denied).filter(project__isnull=False)
    if model_name in ("UserFavorite", "UserRecentVisit"):
        entity_field = "entity_type" if model_name == "UserFavorite" else "entity_name"
        for entity, resource in {
            "issue": "issues",
            "cycle": "cycles",
            "module": "modules",
            "view": "views",
            "page": "pages",
        }.items():
            denied = [a.project_id for a in assignments if not assignment_allows(a, f"{resource}.read")]
            queryset = queryset.exclude(Q(**{f"{entity_field}__iexact": entity}) & Q(project_id__in=denied))
        return queryset
    if model_name == "FileAsset":
        from plane.db.models import Page

        for entity, (permission, relation) in {
            "PAGE_DESCRIPTION": ("pages.read", "page__projects__id"),
            "ISSUE_DESCRIPTION": ("issues.read", "issue__project_id"),
            "COMMENT_DESCRIPTION": ("comments.read", "comment__project_id"),
            "ISSUE_ATTACHMENT": ("attachments.read", "issue__project_id"),
            "DRAFT_ISSUE_DESCRIPTION": ("issues.read", "draft_issue__project_id"),
            "DRAFT_ISSUE_ATTACHMENT": ("attachments.read", "draft_issue__project_id"),
        }.items():
            denied = [a.project_id for a in assignments if not assignment_allows(a, permission)]
            if not denied:
                continue
            if entity == "PAGE_DESCRIPTION":
                visible_pages = scoped_queryset(Page.objects.all(), request_or_user).values("id")
                queryset = queryset.exclude(Q(entity_type=entity) & ~Q(page_id__in=visible_pages))
            else:
                queryset = queryset.exclude(
                    Q(entity_type=entity) & (Q(project_id__in=denied) | Q(**{f"{relation}__in": denied}))
                )
        return queryset
    for permission, lookup in scopes:
        denied = [a.project_id for a in assignments if not assignment_allows(a, permission)]
        if denied:
            if queryset.model.__name__ in ("Page", "PageVersion"):
                from plane.db.models import Project

                user = getattr(request_or_user, "user", request_or_user)
                allowed = (
                    Project.objects.filter(project_projectmember__member=user, project_projectmember__is_active=True)
                    .exclude(pk__in=denied)
                    .values("id")
                )
                queryset = queryset.filter(**{f"{lookup}__in": allowed}).distinct()
            else:
                queryset = queryset.exclude(**{f"{lookup}__in": denied})
    return queryset


def model_is_visible(instance):
    """Protect expanded foreign objects as well as top-level querysets."""
    request = current_role_request.get()
    if request is None or not hasattr(instance, "_meta"):
        return True
    if instance._meta.object_name == "FileAsset":
        return scoped_queryset(type(instance).objects.filter(pk=instance.pk), request).exists()
    scopes = MODEL_SCOPES.get(instance._meta.object_name, ())
    if not scopes:
        return True
    from plane.utils.project_rbac import role_assignments, assignment_allows

    assignments = role_assignments(request)
    for permission, lookup in scopes:
        # Direct project-owned objects are the ones serializers expand. Multi-
        # project pages and relations are scoped by their explicit querysets.
        if lookup == "project_id":
            project_id = getattr(instance, "project_id", None)
            if any(a.project_id == project_id and not assignment_allows(a, permission) for a in assignments):
                return False
    return True


class ScopedPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        queryset = super().get_queryset()
        return scoped_queryset(queryset) if queryset is not None else None


def scoped_aggregate(aggregate):
    """Scope reverse-relation aggregates, whose root is a project/cycle/module."""
    from plane.db.models import Issue, IntakeIssue
    from plane.utils.project_rbac import role_assignments

    request = current_role_request.get()
    if request is None or not role_assignments(request):
        return aggregate
    expression = aggregate.get_source_expressions()[0]
    relation = getattr(expression, "name", "").split("__")[0]
    targets = {
        "issue_cycle": (Issue, "issue_cycle__issue_id"),
        "issue_module": (Issue, "issue_module__issue_id"),
        "project_issue": (Issue, "project_issue__id"),
        "project_intakeissue": (IntakeIssue, "project_intakeissue__id"),
        "issue_intake": (IntakeIssue, "issue_intake__id"),
    }
    if relation in targets:
        model, lookup = targets[relation]
        scope = Q(**{f"{lookup}__in": scoped_queryset(model.objects.all()).values("id")})
        aggregate.filter = aggregate.filter & scope if aggregate.filter is not None else scope
    return aggregate
