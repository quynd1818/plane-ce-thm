from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("db", "0124_customization")]

    operations = [
        migrations.CreateModel(
            name="IntakeForm",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="intakeform_created_by", to="db.user")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="intakeform_updated_by", to="db.user")),
                ("name", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=100)),
                ("description", models.TextField(blank=True, default="")),
                ("fields", models.JSONField(default=list)),
                ("default_values", models.JSONField(default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("public_key", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("intake", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="forms", to="db.intake")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="project_intakeform", to="db.project")),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="workspace_intakeform", to="db.workspace")),
            ],
            options={"db_table": "intake_forms"},
        ),
        migrations.CreateModel(
            name="RecurringIssue",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recurringissue_created_by", to="db.user")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recurringissue_updated_by", to="db.user")),
                ("name", models.CharField(max_length=255)),
                ("description_html", models.TextField(blank=True, default="<p></p>")),
                ("frequency", models.CharField(choices=[("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly")], default="weekly", max_length=20)),
                ("interval", models.PositiveIntegerField(default=1)),
                ("next_run_at", models.DateTimeField()),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("priority", models.CharField(default="none", max_length=30)),
                ("assignee_ids", models.JSONField(default=list)),
                ("label_ids", models.JSONField(default=list)),
                ("custom_properties", models.JSONField(default=dict)),
                ("issue_type", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="db.issuetype")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="project_recurringissue", to="db.project")),
                ("state", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="db.state")),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="workspace_recurringissue", to="db.workspace")),
            ],
            options={"db_table": "recurring_issues", "ordering": ("next_run_at",)},
        ),
        migrations.AddConstraint(
            model_name="intakeform",
            constraint=models.UniqueConstraint(fields=("project", "slug"), condition=models.Q(deleted_at__isnull=True), name="intake_form_unique_project_slug"),
        ),
    ]
