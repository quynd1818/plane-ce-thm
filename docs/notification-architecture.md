# Microsoft Teams Notification Architecture

## Architecture

```text
Django model event
        |
        v
Notification signal
        |
        v
publish_event() -- transaction.on_commit --> Celery
        |
        v
NotificationManager
        |
        +--> TeamsProvider --> Microsoft Teams Incoming Webhook
        +--> EmailProvider (future)
        +--> SlackProvider (future)
```

Model signals keep issue, comment, cycle, project, worklog, customization, recurring issue, and intake workflows independent from provider-specific delivery. Delivery happens after the database transaction commits and does not block the HTTP request.

## Implemented events

- Phase 1: issue created, assigned, updated, and completed; comments; cycles; projects; worklogs and timers.
- Phase 2: custom property, work item template, and work item type changes.
- Phase 3: recurring issue configuration and generation, intake form changes, and intake submissions.
- Dashboard reads are intentionally not notifications because they do not mutate data.

The Teams provider emits an Adaptive Card payload and truncates sanitized description content to 500 characters. Failed webhook requests are logged with `notification_failure` and retried by Celery with exponential backoff up to three times.

## Configuration

Set these variables in the API environment:

```dotenv
TEAMS_ENABLED=true
TEAMS_WEBHOOK_URL=https://...
TEAMS_NOTIFY_ISSUE_CREATED=true
TEAMS_NOTIFY_ISSUE_ASSIGNED=true
TEAMS_NOTIFY_ISSUE_UPDATED=true
TEAMS_NOTIFY_ISSUE_COMPLETED=true
TEAMS_NOTIFY_COMMENT=true
TEAMS_NOTIFY_CYCLE_STARTED=true
TEAMS_NOTIFY_CYCLE_COMPLETED=true
TEAMS_NOTIFY_PROJECT_CREATED=true
TEAMS_NOTIFY_WORKLOG=true
TEAMS_NOTIFY_CUSTOMIZATION=true
TEAMS_NOTIFY_AUTOMATION=true
TEAMS_NOTIFY_INTAKE=true
```

The webhook URL is read only by the backend and is never returned through an API or UI.

## Example message

```text
New Issue Assigned
Project: ERP
Issue: Implement HRM API
Assignee: quynd
Status: Todo
Priority: High
[Open in Plane]
```

## Deployment

1. Add the variables to the API, Celery worker, and Celery beat environment.
2. Restart API, worker, and beat processes.
3. Confirm the worker imports `plane.bgtasks.notification_task`.
4. Create a test issue and verify the Teams channel receives the card.
5. Temporarily set `TEAMS_ENABLED=false` to disable delivery without changing application code.

## Extension

Add a provider implementing the `NotificationProvider` protocol (`send(NotificationEvent)`) and register it in `NotificationManager`. Business handlers and model signals do not need provider-specific changes.
