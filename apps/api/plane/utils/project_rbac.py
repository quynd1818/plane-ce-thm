"""Fail-closed authorization for opt-in restricted project memberships.

Policies are explicit on views, not inferred from HTTP verbs or role names.
Unassigned users keep existing permissions. Existing checks still run afterwards.
"""

from rest_framework.exceptions import PermissionDenied

from plane.db.models import ProjectRoleAssignment, WorkspaceMember

CAPABILITIES = {
    "worklogs.read": "View worklogs",
    "worklogs.export": "Export worklogs (CSV)",
    "issues.read": "View work item names and custom properties",
    "properties.edit": "Edit selected custom properties",
}


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


def enforce_project_role(view, request):
    if not request.user.is_authenticated:
        return
    assignments = assignments_for(request.user)
    slug = view.kwargs.get("slug")
    if slug:
        assignments = assignments.filter(workspace__slug=slug)
    project_id = view.kwargs.get("project_id")
    if getattr(view, "rbac_project_detail", False):
        project_id = project_id or view.kwargs.get("pk")
    # Identifier routes must not be treated as workspace metadata.
    assignment = assignments.first()
    project_assignment = assignments.filter(project_id=project_id).first() if project_id else None
    if assignment is None:
        return
    policy = getattr(view, "rbac_policy", {}).get(request.method)
    if policy == "metadata" and not slug:
        return
    if (
        not WorkspaceMember.objects.using("default")
        .filter(
            workspace_id=assignment.workspace_id,
            member=request.user,
            is_active=True,
        )
        .exists()
    ):
        raise PermissionDenied("Active workspace membership is required.")
    request.project_role_assignment = assignment
    if policy == "metadata":
        return
    # Cross-project aggregates and mutations are unavailable to restricted users:
    # selecting a project in a request body/query must never bypass its role.
    if not project_id:
        raise PermissionDenied("Open a project to use the permissions granted by your custom role.")
    if project_assignment is None:
        raise PermissionDenied(
            "This workspace uses restricted access. Ask an administrator to assign a custom role for this project."
        )
    assignment = project_assignment
    request.project_role_assignment = assignment
    role = assignment.custom_role
    if role.deleted_at or not role.is_active or role.project_id != assignment.project_id:
        raise PermissionDenied("This custom role is disabled. Ask a project administrator.")
    if not policy or policy not in role.permissions:
        raise PermissionDenied("Your custom role does not allow this action.")
    if getattr(view, "rbac_export", False) and request.query_params.get("format") == "csv":
        if "worklogs.export" not in role.permissions:
            raise PermissionDenied("Your custom role does not allow exporting worklogs.")


class ProjectRoleGuardMixin:
    def check_permissions(self, request):
        super().check_permissions(request)
        enforce_project_role(self, request)
