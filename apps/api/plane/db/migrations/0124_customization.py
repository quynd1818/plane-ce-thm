from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("db", "0123_worklog")]

    operations = [
        migrations.AddField(
            model_name="issue",
            name="custom_properties",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name="ProjectCustomProperty",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                ("name", models.CharField(max_length=255)),
                ("key", models.SlugField(max_length=100)),
                ("property_type", models.CharField(choices=[("text", "Text"), ("number", "Number"), ("boolean", "Boolean"), ("date", "Date"), ("select", "Select"), ("multi_select", "Multi select")], default="text", max_length=20)),
                ("options", models.JSONField(blank=True, default=list)),
                ("is_required", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="project_projectcustomproperty", to="db.project")),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="workspace_projectcustomproperty", to="db.workspace")),
            ],
            options={"db_table": "project_custom_properties", "ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="WorkItemTemplate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("defaults", models.JSONField(default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="project_workitemtemplate", to="db.project")),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="workspace_workitemtemplate", to="db.workspace")),
            ],
            options={"db_table": "work_item_templates", "ordering": ("name",)},
        ),
        migrations.AddConstraint(
            model_name="projectcustomproperty",
            constraint=models.UniqueConstraint(
                fields=("project", "key"),
                condition=models.Q(deleted_at__isnull=True),
                name="project_custom_property_unique_key",
            ),
        ),
        migrations.AddConstraint(
            model_name="workitemtemplate",
            constraint=models.UniqueConstraint(
                fields=("project", "name"),
                condition=models.Q(deleted_at__isnull=True),
                name="work_item_template_unique_name",
            ),
        ),
    ]
