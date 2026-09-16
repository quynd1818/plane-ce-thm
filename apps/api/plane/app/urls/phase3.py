from django.urls import path

from plane.app.views.project.phase3 import (
    IntakeFormDetailEndpoint,
    IntakeFormEndpoint,
    ProjectDashboardSummaryEndpoint,
    PublicIntakeFormEndpoint,
    RecurringIssueDetailEndpoint,
    RecurringIssueEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/intake-forms/",
        IntakeFormEndpoint.as_view(),
        name="intake-forms",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/intake-forms/<uuid:form_id>/",
        IntakeFormDetailEndpoint.as_view(),
        name="intake-form-detail",
    ),
    path("public/intake-forms/<uuid:public_key>/", PublicIntakeFormEndpoint.as_view(), name="public-intake-form"),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/recurring-issues/",
        RecurringIssueEndpoint.as_view(),
        name="recurring-issues",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/recurring-issues/<uuid:recurring_id>/",
        RecurringIssueDetailEndpoint.as_view(),
        name="recurring-issue-detail",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/dashboard-summary/",
        ProjectDashboardSummaryEndpoint.as_view(),
        name="project-dashboard-summary",
    ),
]
