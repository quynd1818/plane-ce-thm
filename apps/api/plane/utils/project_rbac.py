"""Fail-closed authorization for opt-in restricted project memberships.

Policies are explicit on views, not inferred from HTTP verbs or role names.
Unassigned users keep existing permissions. Existing checks still run afterwards.
"""

from rest_framework.exceptions import PermissionDenied, NotFound

from plane.db.models import ProjectRoleAssignment, WorkspaceMember

RESOURCE_LABELS = {
    "issues": "Work items",
    "comments": "Comments",
    "attachments": "Attachments",
    "cycles": "Cycles",
    "modules": "Modules",
    "pages": "Pages",
    "views": "Views",
    "intake": "Intake",
    "worklogs": "Worklogs",
    "states": "States",
    "labels": "Labels",
    "estimates": "Estimates",
    "types": "Work item types",
    "templates": "Templates",
    "workflow": "Workflow rules",
    "automation": "Recurring work items",
    "members": "Project members",
    "project": "Project settings",
    "analytics": "Analytics and dashboards",
}
CAPABILITIES = {
    f"{resource}.{action}": f"{label}: {action}"
    for resource, label in RESOURCE_LABELS.items()
    for action in ("read", "create", "update", "delete")
}
CAPABILITIES.update(
    {
        "properties.read": "View work item names and custom properties",
        "properties.edit": "Edit selected custom property values",
        "properties.create": "Create custom property definitions",
        "properties.update": "Update custom property definitions",
        "properties.delete": "Delete custom property definitions",
        "issues.archive": "Archive / restore work items",
        "issues.export": "Export work items",
        "cycles.archive": "Archive / restore cycles",
        "modules.archive": "Archive / restore modules",
        "pages.archive": "Archive / restore pages",
        "pages.lock": "Lock / unlock pages",
        "pages.share": "Change page visibility",
        "pages.export": "Export pages",
        "project.archive": "Archive / restore project",
        "project.publish": "Publish project",
        "worklogs.export": "Export worklogs",
        "worklogs.review": "Review worklogs",
        "analytics.read": "View project analytics",
        "analytics.export": "Export analytics",
    }
)


def assignments_for(user):
    # Keep restrictions after membership soft deletion until an admin explicitly
    # unassigns the role. Otherwise removing membership restores broad workspace access.
    # Read authorization from primary: a replica may lag behind a revocation.
    return (
        ProjectRoleAssignment.all_objects.using("default")
        .filter(
            membership__member=user,
            project__deleted_at__isnull=True,
        )
        .select_related("custom_role", "membership")
    )


def role_assignments(request_or_user):
    user = getattr(request_or_user, "user", request_or_user)
    if not user or not user.is_authenticated:
        return []
    cached = getattr(request_or_user, "_custom_role_assignments", None)
    if cached is not None:
        return cached
    assignments = list(assignments_for(user))
    active_workspaces = (
        set(
            WorkspaceMember.objects.using("default")
            .filter(member=user, is_active=True)
            .values_list("workspace_id", flat=True)
        )
        if assignments
        else set()
    )
    for assignment in assignments:
        assignment.workspace_membership_active = assignment.workspace_id in active_workspaces
    if hasattr(request_or_user, "user"):
        request_or_user._custom_role_assignments = assignments
    return assignments


def assignment_allows(assignment, capability):
    role = assignment.custom_role
    return bool(
        assignment.workspace_membership_active
        and assignment.membership.is_active
        and assignment.membership.deleted_at is None
        and role.deleted_at is None
        and role.is_active
        and role.project_id == assignment.project_id
        and capability in role.permissions
    )


def require_project_capability(request_or_user, project_id, capability):
    for assignment in role_assignments(request_or_user):
        if str(assignment.project_id) == str(project_id):
            permissions = capability if isinstance(capability, (list, tuple)) else [capability]
            if not permissions or any(not assignment_allows(assignment, permission) for permission in permissions):
                raise PermissionDenied("Your custom role does not allow this action in this project.")
            return


def endpoint_policy(view, request):
    from plane.utils.project_rbac_policies import POLICIES

    key = f"{type(view).__module__}.{type(view).__name__}"
    policy = POLICIES.get(key, getattr(view, "rbac_policy", {}))
    return policy.get(getattr(view, "action", None), policy.get("GET" if request.method == "HEAD" else request.method))


def enforce_project_role(view, request):
    from plane.db.models import Project, Issue

    assignments = role_assignments(request)
    request.rbac_has_assignments = bool(assignments)
    if not assignments:
        return
    slug = view.kwargs.get("slug")
    project_id = view.kwargs.get("project_id")
    policy = endpoint_policy(view, request)
    if getattr(view, "rbac_project_detail", False) or type(view).__name__ == "ProjectDetailAPIEndpoint":
        project_id = project_id or view.kwargs.get("pk")
    if view.kwargs.get("project_identifier"):
        project_id = (
            Project.objects.filter(workspace__slug=slug, identifier__iexact=view.kwargs["project_identifier"])
            .values_list("id", flat=True)
            .first()
        )
    # Workspace routes carrying an object ID must authorize the object's project.
    if view.kwargs.get("dashboard_id"):
        from plane.db.models import Dashboard

        project_id = (
            Dashboard.objects.filter(pk=view.kwargs["dashboard_id"], workspace__slug=slug)
            .values_list("project_id", flat=True)
            .first()
        )
    if type(view).__name__ == "WorkspaceDraftIssueViewSet" and (view.kwargs.get("pk") or view.kwargs.get("draft_id")):
        from plane.db.models import DraftIssue

        project_id = (
            DraftIssue.objects.filter(pk=view.kwargs.get("pk") or view.kwargs.get("draft_id"), workspace__slug=slug)
            .values_list("project_id", flat=True)
            .first()
        )
    if getattr(view, "rbac_export", False) and request.query_params.get("format") == "csv":
        policy = ("worklogs.read", "worklogs.export")
    # Resolve object-backed routes before authorizing: the URL project cannot
    # be borrowed to mutate a resource belonging to another project.
    from plane.db.models import Cycle, Module, Page, FileAsset, IssueComment

    resource = policy.split(".")[0] if isinstance(policy, str) else None
    targets = {"issue_id": Issue, "cycle_id": Cycle, "module_id": Module, "page_id": Page}
    if resource in {"issues", "cycles", "modules", "pages", "comments"} and type(view).__name__ in {
        "IssueViewSet",
        "IssueDetailAPIEndpoint",
        "CycleViewSet",
        "ModuleViewSet",
        "PageViewSet",
        "PagesDescriptionViewSet",
        "IssueCommentViewSet",
    }:
        targets["pk"] = {"issues": Issue, "cycles": Cycle, "modules": Module, "pages": Page, "comments": IssueComment}[
            resource
        ]
    for key, model in targets.items():
        object_id = view.kwargs.get(key)
        if object_id and project_id:
            project_lookup = "projects__id" if model is Page else "project_id"
            if not model.objects.filter(pk=object_id, **{project_lookup: project_id}).exists():
                raise NotFound("Resource does not belong to this project.")
    if ".asset." in type(view).__module__ or type(view).__module__ == "plane.api.views.asset":
        data = request.data if request.method not in ("GET", "HEAD") else {}
        asset_id = view.kwargs.get("asset_id") or view.kwargs.get("pk")
        asset = FileAsset.objects.filter(pk=asset_id).first() if asset_id else None
        entity_type = asset.entity_type if asset else data.get("entity_type")
        if asset:
            project_id = project_id or asset.project_id
            for related in ("issue", "comment", "draft_issue"):
                if not project_id and getattr(asset, f"{related}_id", None):
                    project_id = getattr(asset, related).project_id
        entity_id = data.get("entity_identifier")
        model = (
            Page
            if entity_type == "PAGE_DESCRIPTION"
            else IssueComment
            if entity_type == "COMMENT_DESCRIPTION"
            else Issue
        )
        if entity_id and not project_id:
            from uuid import UUID

            try:
                UUID(str(entity_id))
                lookup = "projects__id" if model is Page else "project_id"
                project_id = model.objects.filter(pk=entity_id).values_list(lookup, flat=True).first()
            except (ValueError, TypeError):
                pass
        asset_resource = {
            "PAGE_DESCRIPTION": "pages",
            "ISSUE_DESCRIPTION": "issues",
            "COMMENT_DESCRIPTION": "comments",
            "PROJECT_COVER": "project",
        }.get(entity_type, "attachments")
        action = (
            "read"
            if request.method in ("GET", "HEAD")
            else "update"
            if asset_resource != "attachments"
            else "delete"
            if request.method == "DELETE"
            else "create"
        )
        policy = f"{asset_resource}.{action}"
        if entity_id and request.method not in ("GET", "HEAD"):
            from uuid import UUID

            try:
                UUID(str(entity_id))
                lookup = "projects__id" if model is Page else "project_id"
                for destination in model.objects.filter(pk=entity_id).values_list(lookup, flat=True):
                    require_project_capability(request, destination, policy)
            except (ValueError, TypeError):
                pass  # The endpoint validates malformed entity IDs.

        if asset and asset.page_id:
            linked = list(
                asset.page.projects.filter(
                    project_projectmember__member=request.user, project_projectmember__is_active=True
                ).values_list("id", flat=True)
            )
            if request.method in ("GET", "HEAD"):
                allowed = []
                for linked_project in linked:
                    try:
                        require_project_capability(request, linked_project, policy)
                        allowed.append(linked_project)
                    except PermissionDenied:
                        continue
                if not allowed:
                    raise PermissionDenied("Page asset access is not granted.")
                project_id = allowed[0]
            else:
                for linked_project in linked:
                    require_project_capability(request, linked_project, policy)

        if entity_type in ("USER_AVATAR", "USER_COVER", "WORKSPACE_LOGO", "PROJECT_COVER") and request.method == "GET":
            policy = "metadata"
    extra_page_capabilities = []
    # Generic serializers must not bypass the separate lifecycle capabilities.
    if (
        resource in {"issues", "cycles", "modules", "project"}
        and request.method in ("POST", "PATCH", "PUT")
        and isinstance(request.data, dict)
    ):
        model = {"issues": Issue, "cycles": Cycle, "modules": Module, "project": Project}[resource]
        key = {"issues": "issue_id", "cycles": "cycle_id", "modules": "module_id", "project": "project_id"}[resource]
        object_id = view.kwargs.get(key) or view.kwargs.get("pk")
        instance = model.objects.filter(pk=object_id).first() if object_id else None
        for field, action in {"archived_at": "archive", "deleted_at": "delete"}.items():
            if field not in request.data:
                continue
            if request.data[field] == (getattr(instance, field, None) if instance else None):
                continue
            require_project_capability(request, project_id, f"{resource}.{action}")
    # Updating generic page fields must not bypass dedicated lock/share/archive actions.
    if resource == "pages" and request.method in ("POST", "PATCH", "PUT") and isinstance(request.data, dict):
        existing_page = (
            Page.objects.filter(pk=view.kwargs.get("page_id")).first() if view.kwargs.get("page_id") else None
        )
        for field, capability in {
            "access": "pages.share",
            "is_locked": "pages.lock",
            "archived_at": "pages.archive",
        }.items():
            if field not in request.data:
                continue
            if existing_page is None and (field == "access" or not request.data[field]):
                continue  # Initial visibility belongs to create; default lock/archive values are harmless.
            if existing_page is not None and request.data[field] == getattr(existing_page, field):
                continue
            require_project_capability(request, project_id, capability)
            extra_page_capabilities.append(capability)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        # Shared pages are one object: a write affects every linked project.
        page_id = view.kwargs.get("page_id")
        if page_id and resource == "pages":
            pages = {page_id}
            if policy == "pages.archive":
                frontier = pages.copy()
                while frontier:
                    children = set(Page.all_objects.filter(parent_id__in=frontier).values_list("id", flat=True)) - pages
                    pages |= children
                    frontier = children
            from plane.db.models import ProjectPage

            for affected_project in (
                ProjectPage.objects.filter(page_id__in=pages).values_list("project_id", flat=True).distinct()
            ):
                require_project_capability(request, affected_project, [policy, *extra_page_capabilities])
        if project_id and isinstance(request.data, dict) and "custom_properties" in request.data:
            validate_property_permission(request, project_id, request.data["custom_properties"])
    request.rbac_project_id = project_id
    request.rbac_capability = policy
    if project_id and policy != "metadata":
        require_project_capability(request, project_id, policy or "unclassified")
    # Aggregate endpoints keep their built-in authorization. Their data queries
    # are independently scoped, including queries entered via another project.
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        data = request.data if isinstance(request.data, dict) else {}
        targets = data.get("project_ids", []) or []
        if not isinstance(targets, list):
            targets = [targets]
        targets += [data.get("project_id"), data.get("project")]
        if policy and policy != "metadata":
            for target in targets:
                if isinstance(target, (str, int)):
                    require_project_capability(request, target, policy)
        # Cross-project work item relations/subitems must authorize BOTH ends.
        ids = []
        for key in ("issue_id", "parent", "parent_id", "related_issue", "related_issue_id"):
            value = data.get(key)
            if isinstance(value, str):
                ids.append(value)
        for key in ("issues", "issue_ids", "sub_issue_ids", "epic_ids"):
            value = data.get(key, [])
            if isinstance(value, list):
                ids.extend(v for v in value if isinstance(v, str))
        from uuid import UUID

        valid_ids = []
        for value in ids:
            try:
                valid_ids.append(UUID(value))
            except (ValueError, TypeError):
                pass  # Existing serializers report malformed IDs.
        for related_project in Issue.objects.filter(pk__in=valid_ids).values_list("project_id", flat=True).distinct():
            require_project_capability(
                request, related_project, policy if policy in ("issues.delete", "issues.archive") else "issues.update"
            )


def validate_property_permission(request, project_id, properties):
    if not isinstance(properties, dict) or not properties:
        return
    for assignment in role_assignments(request):
        if str(assignment.project_id) == str(project_id):
            if not assignment_allows(assignment, "properties.edit") or set(properties) - set(
                assignment.custom_role.property_keys
            ):
                raise PermissionDenied("Your role may only change the selected custom properties.")


class ProjectRoleGuardMixin:
    def dispatch(self, request, *args, **kwargs):
        from plane.utils.project_rbac_scope import current_role_request

        token = current_role_request.set(None)
        try:
            return super().dispatch(request, *args, **kwargs)
        finally:
            current_role_request.reset(token)

    def check_permissions(self, request):
        from plane.utils.project_rbac_scope import current_role_request

        current_role_request.set(request)
        super().check_permissions(request)
        enforce_project_role(self, request)

    def scope_queryset(self, queryset):
        from plane.utils.project_rbac_scope import scoped_queryset

        return scoped_queryset(queryset.all(), self.request)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if getattr(request, "rbac_has_assignments", False):
            response["Cache-Control"] = "private, no-store"
        return response
