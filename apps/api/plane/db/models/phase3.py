import uuid

from django.db import models

from .project import ProjectBaseModel


class IntakeForm(ProjectBaseModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True, default="")
    fields = models.JSONField(default=list)
    default_values = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    public_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    intake = models.ForeignKey("db.Intake", on_delete=models.CASCADE, related_name="forms")

    class Meta:
        db_table = "intake_forms"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "slug"],
                condition=models.Q(deleted_at__isnull=True),
                name="intake_form_unique_project_slug",
            )
        ]


class RecurringIssue(ProjectBaseModel):
    FREQUENCY_CHOICES = (
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    )

    name = models.CharField(max_length=255)
    description_html = models.TextField(blank=True, default="<p></p>")
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="weekly")
    interval = models.PositiveIntegerField(default=1)
    next_run_at = models.DateTimeField()
    last_run_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    priority = models.CharField(max_length=30, default="none")
    state = models.ForeignKey("db.State", on_delete=models.SET_NULL, null=True, blank=True)
    issue_type = models.ForeignKey("db.IssueType", on_delete=models.SET_NULL, null=True, blank=True)
    assignee_ids = models.JSONField(default=list)
    label_ids = models.JSONField(default=list)
    custom_properties = models.JSONField(default=dict)
    class Meta:
        db_table = "recurring_issues"
        ordering = ("next_run_at",)
