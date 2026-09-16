from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from .project import ProjectBaseModel


class WorkLog(ProjectBaseModel):
    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="worklogs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="worklogs")
    description = models.TextField(blank=True, default="")
    duration_seconds = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    is_timer = models.BooleanField(default=False)

    class Meta:
        db_table = "work_logs"
        ordering = ("-started_at",)
        indexes = [
            models.Index(fields=["issue", "user", "started_at"]),
            models.Index(fields=["project", "user", "started_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "user"],
                condition=Q(is_timer=True, ended_at__isnull=True, deleted_at__isnull=True),
                name="worklog_one_active_timer_per_project_user",
            )
        ]

    def __str__(self):
        return f"{self.issue_id} {self.user_id} {self.duration_seconds}s"
