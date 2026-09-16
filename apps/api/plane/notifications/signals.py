from django.conf import settings
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver

from plane.db.models import (
    Cycle,
    IntakeForm,
    IntakeIssue,
    Issue,
    IssueComment,
    Project,
    ProjectCustomProperty,
    ProjectIssueType,
    RecurringIssue,
    WorkItemTemplate,
    WorkLog,
)
from plane.notifications.service import publish_event


def _issue_payload(issue, title):
    project = issue.project
    workspace = issue.workspace
    web_url = (getattr(settings, "WEB_URL", "") or "").rstrip("/")
    return {
        "title": title,
        "project_name": project.name,
        "issue_name": issue.name,
        "status": getattr(issue.state, "name", ""),
        "priority": issue.priority,
        "description": issue.description_stripped or "",
        "link": f"{web_url}/{workspace.slug}/projects/{project.id}/issues/{issue.id}" if web_url else "",
    }


@receiver(pre_save, sender=Issue)
def track_issue_state(sender, instance, **kwargs):
    if not instance._state.adding:
        previous = sender.objects.filter(pk=instance.pk).values("state__group").first()
        instance._notification_previous_state = previous.get("state__group") if previous else None


@receiver(pre_save, sender=Cycle)
def track_cycle_dates(sender, instance, **kwargs):
    if not instance._state.adding:
        previous = sender.objects.filter(pk=instance.pk).values("start_date", "end_date").first()
        if previous:
            instance._notification_previous_start = previous["start_date"]
            instance._notification_previous_end = previous["end_date"]


@receiver(post_save, sender=Issue)
def issue_saved(sender, instance, created, **kwargs):
    if created:
        publish_event("issue.created", _issue_payload(instance, "New Issue Created"))
        return
    publish_event("issue.updated", _issue_payload(instance, "Issue Updated"))
    previous = getattr(instance, "_notification_previous_state", None)
    if previous != "completed" and getattr(instance.state, "group", None) == "completed":
        publish_event("issue.completed", _issue_payload(instance, "Issue Completed"))


@receiver(m2m_changed, sender=Issue.assignees.through)
def issue_assigned(sender, instance, action, pk_set, **kwargs):
    if action == "post_add" and pk_set:
        for assignee in instance.assignees.filter(pk__in=pk_set):
            payload = _issue_payload(instance, "New Issue Assigned")
            payload["assignee"] = assignee.display_name or assignee.email
            publish_event("issue.assigned", payload)


@receiver(post_save, sender=IssueComment)
def comment_added(sender, instance, created, **kwargs):
    if created:
        payload = _issue_payload(instance.issue, "New Comment Added")
        payload["description"] = instance.comment_stripped or ""
        publish_event("comment.added", payload)


@receiver(post_save, sender=Cycle)
def cycle_saved(sender, instance, created, **kwargs):
    previous_start = getattr(instance, "_notification_previous_start", None)
    previous_end = getattr(instance, "_notification_previous_end", None)
    from django.utils import timezone

    if instance.start_date and instance.start_date <= timezone.now() and (created or previous_start is None):
        publish_event(
            "cycle.started",
            {"title": "Cycle Started", "project_name": instance.project.name, "issue_name": instance.name},
        )
    if instance.end_date and instance.end_date <= timezone.now() and (created or previous_end is None):
        publish_event(
            "cycle.completed",
            {"title": "Cycle Completed", "project_name": instance.project.name, "issue_name": instance.name},
        )


@receiver(post_save, sender=Project)
def project_created(sender, instance, created, **kwargs):
    if created:
        publish_event("project.created", {"title": "Project Created", "project_name": instance.name})


def _project_payload(instance, title):
    return {"title": title, "project_name": instance.project.name}


@receiver(post_save, sender=WorkLog)
def worklog_saved(sender, instance, created, **kwargs):
    event_name = "worklog.created" if created else "worklog.updated"
    payload = _issue_payload(instance.issue, "Worklog Added" if created else "Worklog Updated")
    payload.update({"duration_seconds": instance.duration_seconds, "user": instance.user.display_name or instance.user.email})
    publish_event(event_name, payload)


@receiver(post_delete, sender=WorkLog)
def worklog_deleted(sender, instance, **kwargs):
    publish_event(
        "worklog.deleted",
        {
            "title": "Worklog Deleted",
            "project_name": instance.project.name,
            "issue_name": instance.issue.name,
            "duration_seconds": instance.duration_seconds,
        },
    )


@receiver(post_save, sender=ProjectCustomProperty)
def custom_property_changed(sender, instance, created, **kwargs):
    publish_event(
        "custom_property.changed",
        _project_payload(instance, "Custom Property Created" if created else "Custom Property Updated"),
    )


@receiver(post_delete, sender=ProjectCustomProperty)
def custom_property_deleted(sender, instance, **kwargs):
    publish_event("custom_property.changed", _project_payload(instance, "Custom Property Deleted"))


@receiver(post_save, sender=WorkItemTemplate)
def template_changed(sender, instance, created, **kwargs):
    publish_event(
        "template.changed",
        _project_payload(instance, "Work Item Template Created" if created else "Work Item Template Updated"),
    )


@receiver(post_delete, sender=WorkItemTemplate)
def template_deleted(sender, instance, **kwargs):
    publish_event("template.changed", _project_payload(instance, "Work Item Template Deleted"))


@receiver(post_save, sender=ProjectIssueType)
def work_item_type_changed(sender, instance, created, **kwargs):
    publish_event(
        "work_item_type.changed",
        _project_payload(instance, "Work Item Type Added" if created else "Work Item Type Updated"),
    )


@receiver(post_delete, sender=ProjectIssueType)
def work_item_type_deleted(sender, instance, **kwargs):
    publish_event("work_item_type.changed", _project_payload(instance, "Work Item Type Removed"))


@receiver(post_save, sender=RecurringIssue)
def recurring_issue_changed(sender, instance, created, **kwargs):
    publish_event(
        "recurring_issue.changed",
        _project_payload(instance, "Recurring Issue Created" if created else "Recurring Issue Updated"),
    )


@receiver(post_delete, sender=RecurringIssue)
def recurring_issue_deleted(sender, instance, **kwargs):
    publish_event("recurring_issue.changed", _project_payload(instance, "Recurring Issue Deleted"))


@receiver(post_save, sender=IntakeForm)
def intake_form_changed(sender, instance, created, **kwargs):
    publish_event(
        "intake_form.changed",
        _project_payload(instance, "Intake Form Created" if created else "Intake Form Updated"),
    )


@receiver(post_delete, sender=IntakeForm)
def intake_form_deleted(sender, instance, **kwargs):
    publish_event("intake_form.changed", _project_payload(instance, "Intake Form Deleted"))


@receiver(post_save, sender=IntakeIssue)
def intake_submitted(sender, instance, created, **kwargs):
    if created:
        payload = _issue_payload(instance.issue, "New Intake Submission")
        payload["source"] = instance.source or "IN_APP"
        publish_event("intake.submitted", payload)
