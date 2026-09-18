from django.urls import path
from plane.app.views.project.roles import (
    ProjectCustomRoleEndpoint,
    ProjectCustomRoleDetailEndpoint,
    ProjectRoleAssignmentEndpoint,
    ProjectRoleMeEndpoint,
    RoleIssueEndpoint,
    RoleIssueDetailEndpoint,
    WorkspaceRoleAccessEndpoint,
)

base = "workspaces/<str:slug>/projects/<uuid:project_id>/"
urlpatterns = [
    path("workspaces/<str:slug>/role-access/", WorkspaceRoleAccessEndpoint.as_view()),
    path(base + "custom-roles/", ProjectCustomRoleEndpoint.as_view()),
    path(base + "custom-roles/<uuid:role_id>/", ProjectCustomRoleDetailEndpoint.as_view()),
    path(base + "role-assignments/<uuid:membership_id>/", ProjectRoleAssignmentEndpoint.as_view()),
    path(base + "custom-role/me/", ProjectRoleMeEndpoint.as_view()),
    path(base + "role-issues/", RoleIssueEndpoint.as_view()),
    path(base + "role-issues/<uuid:issue_id>/", RoleIssueDetailEndpoint.as_view()),
]
