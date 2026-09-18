"""Opt-in project roles. Assignments restrict, never elevate, built-in membership."""

from django.db import models

from .project import ProjectBaseModel


class ProjectCustomRole(ProjectBaseModel):
    name = models.CharField(max_length=100)
    permissions = models.JSONField(default=list)
    property_keys = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "project_custom_roles"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="project_custom_role_unique_name",
            )
        ]


class ProjectRoleAssignment(ProjectBaseModel):
    membership = models.OneToOneField(
        "db.ProjectMember", on_delete=models.CASCADE, related_name="custom_role_assignment"
    )
    custom_role = models.ForeignKey(ProjectCustomRole, on_delete=models.RESTRICT, related_name="assignments")

    class Meta:
        db_table = "project_role_assignments"
