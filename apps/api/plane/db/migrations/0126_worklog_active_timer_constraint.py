from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("db", "0125_phase3")]

    operations = [
        migrations.AddConstraint(
            model_name="worklog",
            constraint=models.UniqueConstraint(
                condition=Q(is_timer=True, ended_at__isnull=True, deleted_at__isnull=True),
                fields=("project", "user"),
                name="worklog_one_active_timer_per_project_user",
            ),
        ),
    ]
