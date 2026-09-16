from django.db import models

from .project import ProjectBaseModel


class ProjectCustomProperty(ProjectBaseModel):
    PROPERTY_TYPES = (
        ("text", "Text"),
        ("number", "Number"),
        ("boolean", "Boolean"),
        ("date", "Date"),
        ("select", "Select"),
        ("multi_select", "Multi select"),
    )

    name = models.CharField(max_length=255)
    key = models.SlugField(max_length=100)
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPES, default="text")
    options = models.JSONField(default=list, blank=True)
    is_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "project_custom_properties"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["project", "key"],
                condition=models.Q(deleted_at__isnull=True),
                name="project_custom_property_unique_key",
            )
        ]


class WorkItemTemplate(ProjectBaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    defaults = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "work_item_templates"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="work_item_template_unique_name",
            )
        ]
