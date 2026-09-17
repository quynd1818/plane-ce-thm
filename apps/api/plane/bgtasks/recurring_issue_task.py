import logging

from celery import shared_task
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone

from plane.db.models import Issue, IssueAssignee, IssueLabel, Label, ProjectMember, RecurringIssue

logger = logging.getLogger("plane.worker")


def _next_run(value, frequency, interval):
    interval = max(1, int(interval or 1))
    if frequency == "daily":
        return value + relativedelta(days=interval)
    if frequency == "monthly":
        return value + relativedelta(months=interval)
    return value + relativedelta(weeks=interval)


def _advance_past(value, frequency, interval, now):
    """Advance the schedule until it is in the future.

    If the beat scheduler was down for several periods we do NOT want to
    back-fill one issue per missed period on every 5-minute tick; one issue
    is created for the overdue schedule and the next run is moved past now.
    """
    next_value = _next_run(value, frequency, interval)
    while next_value <= now:
        next_value = _next_run(next_value, frequency, interval)
    return next_value


@shared_task
def create_due_recurring_issues():
    now = timezone.now()
    created = 0
    due_ids = RecurringIssue.objects.filter(
        is_active=True, next_run_at__lte=now, deleted_at__isnull=True
    ).values_list("id", flat=True)
    for recurring_id in due_ids:
        try:
            created += _process_recurring_issue(recurring_id, now)
        except Exception:
            logger.exception("recurring_issue_failed", extra={"recurring_issue_id": str(recurring_id)})
    return created


def _process_recurring_issue(recurring_id, now):
    with transaction.atomic():
        recurring = (
            RecurringIssue.objects.select_for_update()
            .select_related("project", "workspace", "state", "issue_type")
            .filter(pk=recurring_id, is_active=True, next_run_at__lte=now, deleted_at__isnull=True)
            .first()
        )
        if recurring is None:
            return 0
        issue = Issue.objects.create(
            project=recurring.project,
            workspace=recurring.workspace,
            name=recurring.name,
            description_html=recurring.description_html,
            priority=recurring.priority,
            state=recurring.state or recurring.project.default_state,
            type=recurring.issue_type,
            custom_properties=recurring.custom_properties,
        )
        # Only keep ids that are still valid: members may have been removed
        # and labels deleted since the recurring issue was configured. A stale
        # id would raise an FK IntegrityError and roll back the whole run.
        valid_assignee_ids = list(
            ProjectMember.objects.filter(
                project=recurring.project,
                member_id__in=recurring.assignee_ids or [],
                is_active=True,
            ).values_list("member_id", flat=True)
        )
        valid_label_ids = list(
            Label.objects.filter(
                project=recurring.project,
                id__in=recurring.label_ids or [],
            ).values_list("id", flat=True)
        )
        IssueAssignee.objects.bulk_create(
            [
                IssueAssignee(
                    issue=issue,
                    assignee_id=user_id,
                    project=recurring.project,
                    workspace=recurring.workspace,
                )
                for user_id in valid_assignee_ids
            ],
            ignore_conflicts=True,
        )
        IssueLabel.objects.bulk_create(
            [
                IssueLabel(
                    issue=issue,
                    label_id=label_id,
                    project=recurring.project,
                    workspace=recurring.workspace,
                )
                for label_id in valid_label_ids
            ],
            ignore_conflicts=True,
        )
        recurring.last_run_at = now
        recurring.next_run_at = _advance_past(recurring.next_run_at, recurring.frequency, recurring.interval, now)
        recurring.save(update_fields=["last_run_at", "next_run_at", "updated_at"])
        return 1
