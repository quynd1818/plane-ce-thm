# Plane Pro features to consider for CE

## Purpose

This document lists the Plane Pro and related Business capabilities that are
useful for a self-hosted Community Edition instance. It is a product
prioritization document, not a license implementation plan. Features should be
protected by existing project/workspace capability flags where needed, without
introducing a cloud-only license check.

The comparison is based on the current Plane pricing and documentation pages:

- <https://plane.so/pricing>
- <https://docs.plane.so/>

## Recommended order

1. Complete time tracking and worklogs.
2. Work item types.
3. Custom properties.
4. Work item and page templates.
5. Dashboards and widgets.
6. Milestones and project overview.
7. Advanced views and exports.
8. GitHub, GitLab, Slack, and Sentry integrations.
9. Recurring work items.
10. Intake forms.
11. Approval workflows.
12. Audit logs and granular RBAC.

## Group A: time tracking and worklogs

### Target behavior

- Start and stop a timer from an issue.
- Prevent more than one active timer for a user in a project.
- Add historical work manually.
- Edit and delete worklogs according to author/admin permissions.
- Filter reports by date range, user, and work item.
- Group totals by work item, user, or day.
- Export the filtered report as CSV.
- Keep the feature behind `Project.is_time_tracking_enabled`.
- Preserve timezone-aware timestamps and project membership checks.

### Remaining implementation work

- Add an edit flow in the issue worklog panel.
- Make delete actions explicit and safe.
- Add report filters and a readable summary by user/work item/day.
- Make report and summary endpoints enforce project membership consistently.
- Add backend coverage for permissions, timer conflicts, feature flags, and
  report filters.
- Run the migration and API tests against the Docker PostgreSQL stack.

## Group B: customization

### Work item types

Allow projects to define types such as Bug, Story, Incident, Feature, or
Support Request. A type can provide defaults for state, priority, labels,
estimate, and templates.

### Custom properties

Support project-level fields such as severity, customer, environment, billing
code, target release, and business value. Values should be typed and filterable
through the existing issue list and view mechanisms.

### Templates

Provide reusable work item templates and project templates. A template should
be able to define description, state, priority, labels, assignee, estimate,
module, cycle, and custom property defaults.

## Group C: reporting and planning

### Dashboards

Useful initial widgets:

- Work items by state.
- Overdue work items.
- Cycle progress and burndown.
- Workload by member.
- Worklogs by member and work item.
- Opened versus completed trend.
- Unassigned work items.

### Milestones and initiatives

Milestones provide release or phase checkpoints. Initiatives group projects
and milestones around a larger objective. These should be introduced after
project overview and reporting queries are stable.

### Advanced views and exports

Expand the current CSV report with saved filters, public/private views, and
additional export formats only when there is a concrete operational need.

## Group D: automation and collaboration

- Recurring work items for scheduled operational work.
- Intake forms that map submissions to projects, work item types, and labels.
- Approval workflows for controlled state transitions.
- GitHub/GitLab/Slack/Sentry integrations.
- Audit logs and more granular workspace/project permissions.

## Deliberate non-goals

- Cloud AI credit accounting should not be copied into self-hosted CE.
  If AI is needed, use a configurable provider such as Azure OpenAI, OpenAI,
  or Ollama with explicit workspace limits.
- LDAP should not be implemented directly while Keycloak can broker LDAP,
  Active Directory, and other OIDC providers.
- Enterprise-grade granular access control should follow an explicit
  permission matrix and audit-log design rather than incremental ad-hoc checks.

## Suggested delivery phases

### Phase 1

Finish worklogs, migrations, permission tests, reporting filters, CSV export,
and Docker-backed backend validation.

### Phase 2

Implement work item types, custom properties, templates, milestones, and
advanced views.

### Phase 3

Implement dashboards, initiatives, audit logs, and stronger RBAC.

### Phase 4

Implement recurring work items, intake forms, approvals, and integrations.
