from dateutil.relativedelta import relativedelta
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from plane.db.models import Issue, IssueAssignee, IssueLabel, RecurringIssue


def _next_run(value, frequency, interval):
    if frequency == "daily":
        return value + relativedelta(days=interval)
    if frequency == "monthly":
        return value + relativedelta(months=interval)
    return value + relativedelta(weeks=interval)


@shared_task
def create_due_recurring_issues():
    now = timezone.now()
    created = 0
    due_ids = RecurringIssue.objects.filter(
        is_active=True, next_run_at__lte=now, deleted_at__isnull=True
    ).values_list("id", flat=True)
    for recurring_id in due_ids:
        with transaction.atomic():
            recurring = (
                RecurringIssue.objects.select_for_update()
                .select_related("project", "workspace", "state", "issue_type")
                .filter(pk=recurring_id, is_active=True, next_run_at__lte=now, deleted_at__isnull=True)
                .first()
            )
            if recurring is None:
                continue
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
            IssueAssignee.objects.bulk_create(
                [
                    IssueAssignee(
                        issue=issue,
                        assignee_id=user_id,
                        project=recurring.project,
                        workspace=recurring.workspace,
                    )
                    for user_id in recurring.assignee_ids
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
                    for label_id in recurring.label_ids
                ],
                ignore_conflicts=True,
            )
            recurring.last_run_at = now
            recurring.next_run_at = _next_run(recurring.next_run_at, recurring.frequency, recurring.interval)
            recurring.save(update_fields=["last_run_at", "next_run_at", "updated_at"])
            created += 1
    return created
