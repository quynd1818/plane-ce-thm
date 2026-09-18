"""Reviewed endpoint policy catalog. Unclassified project endpoints fail closed.

Read scopes are independently enforced by scoped_queryset, including when an
endpoint is entered through a project without a custom role.
"""

POLICIES = {}


def register(module, classes, resource, **overrides):
    policy = {
        "GET": f"{resource}.read",
        "POST": f"{resource}.create",
        "PATCH": f"{resource}.update",
        "PUT": f"{resource}.update",
        "DELETE": f"{resource}.delete",
    }
    policy.update(overrides)
    for name in classes.split():
        POLICIES[f"plane.{module}.{name}"] = policy.copy()


register(
    "app.views.issue.base",
    "IssueListEndpoint IssueViewSet IssuePaginatedViewSet IssueDetailEndpoint "
    "IssueDetailIdentifierEndpoint DeletedIssuesListViewSet",
    "issues",
)
register("app.views.issue.base", "BulkDeleteIssuesEndpoint", "issues")
register("app.views.issue.base", "IssueBulkUpdateDateEndpoint", "issues", POST="issues.update")
register(
    "app.views.issue.base",
    "IssueMetaEndpoint ProjectUserDisplayPropertyEndpoint",
    "metadata",
    GET="metadata",
    PATCH="metadata",
)
register(
    "app.views.issue.archive",
    "IssueArchiveViewSet BulkArchiveIssuesEndpoint",
    "issues",
    POST="issues.archive",
    archive="issues.archive",
    unarchive="issues.archive",
)
register("app.views.issue.sub_issue", "SubIssuesEndpoint", "issues", POST="issues.update")
register(
    "app.views.issue.relation", "IssueRelationViewSet", "issues", POST="issues.update", remove_relation="issues.update"
)
register("app.views.issue.link", "IssueLinkViewSet", "issues", POST="issues.update", DELETE="issues.update")
register("app.views.issue.activity", "IssueActivityEndpoint", "issues")
register("app.views.issue.version", "IssueVersionEndpoint WorkItemDescriptionVersionEndpoint", "issues")
register("app.views.issue.comment", "IssueCommentViewSet", "comments")
register("app.views.issue.comment", "CommentReactionViewSet", "comments", POST="comments.read", DELETE="comments.read")
register("app.views.issue.reaction", "IssueReactionViewSet", "issues", POST="issues.read", DELETE="issues.read")
register(
    "app.views.issue.subscriber",
    "IssueSubscriberViewSet",
    "issues",
    POST="issues.read",
    DELETE="issues.read",
    subscribe="issues.read",
    unsubscribe="issues.read",
    subscription_status="issues.read",
)
register("app.views.issue.attachment", "IssueAttachmentEndpoint IssueAttachmentV2Endpoint", "attachments")
register(
    "app.views.issue.worklog",
    "IssueWorkLogEndpoint IssueWorkLogDetailEndpoint ProjectWorkLogSummaryEndpoint ProjectWorkLogReportEndpoint",
    "worklogs",
)
register("app.views.issue.worklog", "IssueTimerEndpoint", "worklogs", POST="worklogs.create", DELETE="worklogs.update")
register(
    "app.views.issue.worklog",
    "ProjectWorkLogPendingEndpoint WorkLogReviewEndpoint",
    "worklogs",
    GET="worklogs.review",
    POST="worklogs.review",
)
register("app.views.issue.label", "LabelViewSet BulkCreateIssueLabelsEndpoint", "labels", GET="metadata")
register("app.views.cycle.base", "CycleViewSet", "cycles")
register("app.views.cycle.base", "CycleDateCheckEndpoint", "cycles", POST="cycles.read")
register("app.views.cycle.base", "TransferCycleIssueEndpoint", "cycles", POST=("cycles.update", "issues.update"))
register(
    "app.views.cycle.base",
    "CycleFavoriteViewSet CycleUserPropertiesEndpoint",
    "cycles",
    POST="cycles.read",
    PATCH="cycles.read",
    DELETE="cycles.read",
)
register(
    "app.views.cycle.base",
    "CycleProgressEndpoint CycleAnalyticsEndpoint",
    "cycles",
    GET=("cycles.read", "analytics.read"),
)
register(
    "app.views.cycle.issue",
    "CycleIssueViewSet",
    "cycles",
    POST=("cycles.update", "issues.update"),
    DELETE=("cycles.update", "issues.update"),
)
register(
    "app.views.cycle.archive", "CycleArchiveUnarchiveEndpoint", "cycles", POST="cycles.archive", DELETE="cycles.archive"
)
register("app.views.module.base", "ModuleViewSet", "modules")
register("app.views.module.base", "ModuleLinkViewSet", "modules", POST="modules.update", DELETE="modules.update")
register(
    "app.views.module.base",
    "ModuleFavoriteViewSet ModuleUserPropertiesEndpoint",
    "modules",
    POST="modules.read",
    PATCH="modules.read",
    DELETE="modules.read",
)
register(
    "app.views.module.issue",
    "ModuleIssueViewSet",
    "modules",
    POST=("modules.update", "issues.update"),
    DELETE=("modules.update", "issues.update"),
)
register(
    "app.views.module.archive",
    "ModuleArchiveUnarchiveEndpoint",
    "modules",
    POST="modules.archive",
    DELETE="modules.archive",
)
register(
    "app.views.page.base",
    "PageViewSet PagesDescriptionViewSet PageDuplicateEndpoint",
    "pages",
    lock="pages.lock",
    unlock="pages.lock",
    access="pages.share",
    archive="pages.archive",
    unarchive="pages.archive",
    summary="pages.read",
)
register("app.views.page.base", "PageFavoriteViewSet", "pages", POST="pages.read", DELETE="pages.read")
register("app.views.page.version", "PageVersionEndpoint", "pages")
register("app.views.view.base", "IssueViewViewSet", "views")
register("app.views.view.base", "IssueViewFavoriteViewSet", "views", POST="views.read", DELETE="views.read")
register("app.views.intake.base", "IntakeViewSet IntakeIssueViewSet IntakeWorkItemDescriptionVersionEndpoint", "intake")
register(
    "app.views.state.base",
    "StateViewSet IntakeStateEndpoint",
    "states",
    GET="metadata",
    mark_as_default="states.update",
)
register(
    "app.views.estimate.base",
    "ProjectEstimatePointEndpoint BulkEstimatePointEndpoint EstimatePointEndpoint",
    "estimates",
    GET="metadata",
)
register("app.views.project.base", "ProjectViewSet", "project", GET="metadata")
register(
    "app.views.project.base",
    "ProjectArchiveUnarchiveEndpoint",
    "project",
    POST="project.archive",
    DELETE="project.archive",
)
register(
    "app.views.project.base",
    "ProjectUserViewsEndpoint ProjectFavoritesViewSet",
    "project",
    GET="metadata",
    POST="metadata",
    DELETE="metadata",
)
register(
    "app.views.project.base",
    "DeployBoardViewSet",
    "project",
    GET="project.publish",
    POST="project.publish",
    DELETE="project.publish",
)
register("app.views.project.member", "ProjectMemberViewSet", "members", GET="metadata", leave="metadata")
register(
    "app.views.project.member",
    "ProjectMemberUserEndpoint ProjectMemberPreferenceEndpoint",
    "members",
    GET="metadata",
    PATCH="metadata",
)
register("app.views.project.invite", "ProjectInvitationsViewset", "members")
register("app.views.project.invite", "ProjectJoinEndpoint", "members", GET="metadata", POST="metadata")
register(
    "app.views.project.customization",
    "ProjectCustomPropertyEndpoint ProjectCustomPropertyDetailEndpoint",
    "properties",
    GET="metadata",
)
register(
    "app.views.project.customization",
    "WorkItemTemplateEndpoint WorkItemTemplateDetailEndpoint",
    "templates",
    GET="templates.read",
)
register(
    "app.views.project.customization",
    "ProjectIssueTypeEndpoint ProjectIssueTypeDetailEndpoint",
    "types",
    GET="metadata",
)
register(
    "app.views.project.workflow",
    "WorkflowTransitionRuleEndpoint WorkflowTransitionRuleDetailEndpoint",
    "workflow",
    GET="metadata",
)
register("app.views.project.workflow", "WorkflowAllowedStatesEndpoint", "issues")
register("app.views.project.phase3", "IntakeFormEndpoint IntakeFormDetailEndpoint", "intake")
register("app.views.project.phase3", "RecurringIssueEndpoint RecurringIssueDetailEndpoint", "automation")
register("app.views.project.phase3", "ProjectDashboardSummaryEndpoint", "analytics")
register(
    "app.views.project.epic",
    "ProjectEpicDetailEndpoint ProjectEpicWorkItemsEndpoint ProjectEpicConvertEndpoint",
    "issues",
    POST="issues.update",
)
register("app.views.project.template", "ProjectSaveAsTemplateEndpoint", "templates", POST="templates.create")
register(
    "app.views.analytic.project_analytics",
    "ProjectAdvanceAnalyticsEndpoint ProjectAdvanceAnalyticsStatsEndpoint ProjectAdvanceAnalyticsChartEndpoint",
    "analytics",
)
register("app.views.analytic.base", "ProjectStatsEndpoint", "analytics")
register(
    "app.views.asset.v2", "ProjectAssetEndpoint ProjectBulkAssetEndpoint ProjectAssetDownloadEndpoint", "attachments"
)
register("app.views.external.base", "GPTIntegrationEndpoint", "issues", POST="issues.update")
# Public API uses the same capability names.
register(
    "api.views.issue",
    "WorkspaceIssueAPIEndpoint IssueListCreateAPIEndpoint IssueDetailAPIEndpoint "
    "IssueActivityListAPIEndpoint IssueActivityDetailAPIEndpoint IssueSearchEndpoint",
    "issues",
)
register(
    "api.views.issue",
    "IssueLinkListCreateAPIEndpoint IssueLinkDetailAPIEndpoint IssueRelationListCreateAPIEndpoint",
    "issues",
    POST="issues.update",
    DELETE="issues.update",
)
register("api.views.issue", "IssueCommentListCreateAPIEndpoint IssueCommentDetailAPIEndpoint", "comments")
register("api.views.issue", "IssueAttachmentListCreateAPIEndpoint IssueAttachmentDetailAPIEndpoint", "attachments")
register("api.views.issue", "LabelListCreateAPIEndpoint LabelDetailAPIEndpoint", "labels", GET="metadata")
register("api.views.cycle", "CycleListCreateAPIEndpoint CycleListLiteAPIEndpoint CycleDetailAPIEndpoint", "cycles")
register(
    "api.views.cycle", "CycleArchiveUnarchiveAPIEndpoint", "cycles", POST="cycles.archive", DELETE="cycles.archive"
)
register(
    "api.views.cycle",
    "CycleIssueListCreateAPIEndpoint CycleIssueDetailAPIEndpoint TransferCycleIssueAPIEndpoint",
    "cycles",
    POST=("cycles.update", "issues.update"),
    DELETE=("cycles.update", "issues.update"),
)
register("api.views.module", "ModuleListCreateAPIEndpoint ModuleListLiteAPIEndpoint ModuleDetailAPIEndpoint", "modules")
register(
    "api.views.module",
    "ModuleIssueListCreateAPIEndpoint ModuleIssueDetailAPIEndpoint",
    "modules",
    POST=("modules.update", "issues.update"),
    DELETE=("modules.update", "issues.update"),
)
register(
    "api.views.module", "ModuleArchiveUnarchiveAPIEndpoint", "modules", POST="modules.archive", DELETE="modules.archive"
)
register("api.views.intake", "IntakeIssueListCreateAPIEndpoint IntakeIssueDetailAPIEndpoint", "intake")
register(
    "api.views.estimate",
    "ProjectEstimateAPIEndpoint EstimatePointListCreateAPIEndpoint EstimatePointDetailAPIEndpoint",
    "estimates",
    GET="metadata",
)
register("api.views.state", "StateListCreateAPIEndpoint StateDetailAPIEndpoint", "states", GET="metadata")
register(
    "api.views.member",
    "ProjectMemberListCreateAPIEndpoint ProjectMemberDetailAPIEndpoint ProjectMemberLiteAPIEndpoint",
    "members",
    GET="metadata",
)
register("api.views.project", "ProjectDetailAPIEndpoint", "project", GET="metadata")
register(
    "api.views.project",
    "ProjectArchiveUnarchiveAPIEndpoint",
    "project",
    POST="project.archive",
    DELETE="project.archive",
)
register("api.views.project", "ProjectSummaryAPIEndpoint", "analytics")

# Workspace-scoped writes with an optional project target must check that target.
register("app.views.workspace.draft", "WorkspaceDraftIssueViewSet", "issues")
register(
    "app.views.workspace.dashboard",
    "DashboardEndpoint DashboardDetailEndpoint DashboardWidgetEndpoint "
    "DashboardWidgetDetailEndpoint DashboardWidgetReorderEndpoint",
    "analytics",
)
register("app.views.project.template", "ProjectTemplateEndpoint ProjectTemplateDetailEndpoint", "templates")
register("app.views.search.issue", "IssueSearchEndpoint", "issues")
register(
    "app.views.analytic.base",
    "AnalyticsEndpoint AnalyticViewViewset SavedAnalyticEndpoint DefaultAnalyticsEndpoint",
    "analytics",
)
register(
    "app.views.analytic.base", "ExportAnalyticsEndpoint", "analytics", POST="analytics.export", GET="analytics.export"
)
register(
    "app.views.analytic.advance",
    "AdvanceAnalyticsEndpoint AdvanceAnalyticsStatsEndpoint AdvanceAnalyticsChartEndpoint",
    "analytics",
)
register("app.views.workspace.base", "UserWorkspaceDashboardEndpoint", "analytics")
register(
    "app.views.workspace.user",
    "WorkspaceUserProfileStatsEndpoint UserActivityGraphEndpoint UserIssueCompletedGraphEndpoint",
    "analytics",
)
register("app.views.workspace.dashboard", "DashboardWidgetDataEndpoint DashboardDataEndpoint", "analytics")
register("app.views.workspace.initiative", "InitiativeAnalyticsEndpoint", "analytics")

register(
    "app.views.workspace.initiative",
    "InitiativeProjectsEndpoint InitiativeEpicsEndpoint",
    "issues",
    POST="issues.update",
    DELETE="issues.update",
)

register("app.views.project.epic", "ProjectEpicEndpoint", "issues")
