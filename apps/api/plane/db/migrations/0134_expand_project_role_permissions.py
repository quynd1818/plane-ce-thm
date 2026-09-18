from django.db import migrations


def forwards(apps, schema_editor):
    Role = apps.get_model("db", "ProjectCustomRole")
    for role in Role.objects.using(schema_editor.connection.alias).all().iterator():
        if "issues.read" in role.permissions:
            role.permissions = sorted({"properties.read" if p == "issues.read" else p for p in role.permissions})
            role.save(update_fields=["permissions"])


def backwards(apps, schema_editor):
    Role = apps.get_model("db", "ProjectCustomRole")
    for role in Role.objects.using(schema_editor.connection.alias).all().iterator():
        role.permissions = sorted({"issues.read" if p == "properties.read" else p for p in role.permissions})
        role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [("db", "0133_project_custom_roles")]
    operations = [migrations.RunPython(forwards, backwards)]
