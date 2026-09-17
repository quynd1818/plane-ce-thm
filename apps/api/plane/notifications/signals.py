from django.conf import settings
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

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
    User,
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


# Fields whose change is worth a Teams message. Every other Issue.save()
# (sort_order drags, description autosave, sequence updates, ...) is ignored,
# otherwise the channel gets flooded.
ISSUE_NOTIFY_FIELDS = ("name", "state_id", "priority", "target_date", "start_date")


@receiver(pre_save, sender=Issue)
def track_issue_state(sender, instance, **kwargs):
    if instance._state.adding:
        return
    # all_objects: the default manager hides soft-deleted rows, which would make
    # every re-save of a deleted issue look like a fresh delete.
    previous = (
        sender.all_objects.filter(pk=instance.pk)
        .values("state__group", "deleted_at", *ISSUE_NOTIFY_FIELDS)
        .first()
    )
    if not previous:
        return
    instance._notification_previous_state = previous.get("state__group")
    instance._notification_previous_deleted_at = previous.get("deleted_at")
    instance._notification_changed = any(
        getattr(instance, field, None) != previous.get(field) for field in ISSUE_NOTIFY_FIELDS
    )


@receiver(pre_save, sender=Cycle)
def track_cycle_dates(sender, instance, **kwargs):
    if not instance._state.adding:
        previous = sender.objects.filter(pk=instance.pk).values("start_date", "end_date").first()
        if previous:
            instance._notification_previous_start = previous["start_date"]
            instance._notification_previous_end = previous["end_date"]


@receiver(post_save, sender=Issue)
def issue_saved(sender, instance, created, raw=False, **kwargs):
    if raw or getattr(instance, "is_draft", False):
        return
    if created:
        if instance.deleted_at is None:
            publish_event("issue.created", _issue_payload(instance, "New Issue Created"))
        return
    # Soft delete: Plane never fires post_delete for issues, it sets deleted_at.
    if instance.deleted_at is not None:
        if getattr(instance, "_notification_previous_deleted_at", None) is None:
            publish_event("issue.deleted", _issue_payload(instance, "Issue Deleted"))
        return
    previous = getattr(instance, "_notification_previous_state", None)
    if previous != "completed" and getattr(instance.state, "group", None) == "completed":
        publish_event("issue.completed", _issue_payload(instance, "Issue Completed"))
        return
    if getattr(instance, "_notification_changed", False):
        publish_event("issue.updated", _issue_payload(instance, "Issue Updated"))


def notify_issue_assigned(issue, assignee_ids):
    """Publish one issue.assigned event per newly added assignee.

    Plane writes assignees with IssueAssignee.objects.bulk_create(), which fires
    neither m2m_changed nor post_save, so the serializers call this explicitly.
    """
    if not assignee_ids or getattr(issue, "is_draft", False):
        return
    for assignee in User.objects.filter(pk__in=assignee_ids):
        payload = _issue_payload(issue, "New Issue Assigned")
        payload["assignee"] = assignee.display_name or assignee.email
        publish_event("issue.assigned", payload)


@receiver(m2m_changed, sender=Issue.assignees.through)
def issue_assigned(sender, instance, action, pk_set, **kwargs):
    # Only reached when assignees are changed through the M2M manager.
    if action == "post_add" and pk_set:
        notify_issue_assigned(instance, pk_set)


@receiver(post_save, sender=IssueComment)
def comment_added(sender, instance, created, raw=False, **kwargs):
    if created and not raw and instance.deleted_at is None:
        payload = _issue_payload(instance.issue, "New Comment Added")
        payload["description"] = instance.comment_stripped or ""
        publish_event("comment.added", payload)


@receiver(post_save, sender=Cycle)
def cycle_saved(sender, instance, created, raw=False, **kwargs):
    if raw or instance.deleted_at is not None:
        return
    previous_start = getattr(instance, "_notification_previous_start", None)
    previous_end = getattr(instance, "_notification_previous_end", None)

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
def project_created(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        publish_event("project.created", {"title": "Project Created", "project_name": instance.name})


def _project_payload(instance, title):
    return {"title": title, "project_name": instance.project.name}


@receiver(post_save, sender=WorkLog)
def worklog_saved(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    if instance.deleted_at is not None:
        # soft delete goes through save(), not post_delete
        worklog_deleted(sender, instance)
        return
    if instance.is_timer and instance.ended_at is None:
        # running timer: nothing meaningful to report yet
        return
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
def custom_property_changed(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    if instance.deleted_at is not None:
        title = "Custom Property Deleted"
    elif created:
        title = "Custom Property Created"
    else:
        title = "Custom Property Updated"
    publish_event("custom_property.changed", _project_payload(instance, title))


@receiver(post_delete, sender=ProjectCustomProperty)
def custom_property_deleted(sender, instance, **kwargs):
    publish_event("custom_property.changed", _project_payload(instance, "Custom Property Deleted"))


@receiver(post_save, sender=WorkItemTemplate)
def template_changed(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    if instance.deleted_at is not None:
        title = "Work Item Template Deleted"
    elif created:
        title = "Work Item Template Created"
    else:
        title = "Work Item Template Updated"
    publish_event("template.changed", _project_payload(instance, title))


@receiver(post_delete, sender=WorkItemTemplate)
def template_deleted(sender, instance, **kwargs):
    publish_event("template.changed", _project_payload(instance, "Work Item Template Deleted"))


@receiver(post_save, sender=ProjectIssueType)
def work_item_type_changed(sender, instance, created, raw=False, **kwargs):
    if raw or getattr(instance, "deleted_at", None) is not None:
        return
    publish_event(
        "work_item_type.changed",
        _project_payload(instance, "Work Item Type Added" if created else "Work Item Type Updated"),
    )


@receiver(post_delete, sender=ProjectIssueType)
def work_item_type_deleted(sender, instance, **kwargs):
    publish_event("work_item_type.changed", _project_payload(instance, "Work Item Type Removed"))


@receiver(post_save, sender=RecurringIssue)
def recurring_issue_changed(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    if instance.deleted_at is not None:
        title = "Recurring Issue Deleted"
    elif created:
        title = "Recurring Issue Created"
    else:
        title = "Recurring Issue Updated"
    publish_event("recurring_issue.changed", _project_payload(instance, title))


@receiver(post_delete, sender=RecurringIssue)
def recurring_issue_deleted(sender, instance, **kwargs):
    publish_event("recurring_issue.changed", _project_payload(instance, "Recurring Issue Deleted"))


@receiver(post_save, sender=IntakeForm)
def intake_form_changed(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    if instance.deleted_at is not None:
        title = "Intake Form Deleted"
    elif created:
        title = "Intake Form Created"
    else:
        title = "Intake Form Updated"
    publish_event("intake_form.changed", _project_payload(instance, title))


@receiver(post_delete, sender=IntakeForm)
def intake_form_deleted(sender, instance, **kwargs):
    publish_event("intake_form.changed", _project_payload(instance, "Intake Form Deleted"))


@receiver(post_save, sender=IntakeIssue)
def intake_submitted(sender, instance, created, raw=False, **kwargs):
    if created and not raw and instance.deleted_at is None:
        payload = _issue_payload(instance.issue, "New Intake Submission")
        payload["source"] = instance.source or "IN_APP"
        publish_event("intake.submitted", payload)
