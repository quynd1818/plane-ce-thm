from rest_framework import serializers

from plane.db.models import IntakeForm, IssueType, Label, ProjectMember, RecurringIssue, State


class IntakeFormSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntakeForm
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "fields",
            "default_values",
            "is_active",
            "public_key",
            "intake",
        ]
        read_only_fields = ["id", "public_key", "intake"]

    def validate_fields(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Fields must be a list.")
        keys = set()
        allowed_types = {"text", "textarea", "number", "date", "email", "select"}
        for field in value:
            if not isinstance(field, dict) or not field.get("key") or not field.get("label"):
                raise serializers.ValidationError("Each field requires a key and label.")
            key = str(field["key"])
            if key in keys:
                raise serializers.ValidationError(f"Field key '{key}' must be unique.")
            if field.get("type", "text") not in allowed_types:
                raise serializers.ValidationError("Unsupported intake field type.")
            if field.get("type") == "select" and not isinstance(field.get("options"), list):
                raise serializers.ValidationError("Select fields require an options list.")
            keys.add(key)
        return value

    def validate_default_values(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Default values must be an object.")
        return value

    def validate(self, attrs):
        fields = attrs.get("fields", self.instance.fields if self.instance else [])
        default_values = attrs.get(
            "default_values", self.instance.default_values if self.instance else {}
        )
        field_keys = {field["key"] for field in fields}
        unknown_defaults = set(default_values) - field_keys
        if unknown_defaults:
            raise serializers.ValidationError(
                {"default_values": f"Unknown fields: {sorted(unknown_defaults)}"}
            )
        return attrs


class RecurringIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurringIssue
        fields = [
            "id",
            "name",
            "description_html",
            "frequency",
            "interval",
            "next_run_at",
            "last_run_at",
            "is_active",
            "priority",
            "state",
            "issue_type",
            "assignee_ids",
            "label_ids",
            "custom_properties",
        ]
        read_only_fields = ["id", "last_run_at"]

    def validate_interval(self, value):
        if value < 1:
            raise serializers.ValidationError("Interval must be at least 1.")
        return value

    def validate(self, attrs):
        project_id = self.context.get("project_id")
        if not project_id:
            return attrs

        state = attrs.get("state", self.instance.state if self.instance else None)
        if state and not State.objects.filter(pk=state.pk, project_id=project_id).exists():
            raise serializers.ValidationError({"state": "State does not belong to this project."})

        issue_type = attrs.get("issue_type", self.instance.issue_type if self.instance else None)
        if issue_type and not IssueType.objects.filter(
            pk=issue_type.pk,
            workspace_id=self.context.get("workspace_id"),
            is_active=True,
        ).exists():
            raise serializers.ValidationError({"issue_type": "Work item type does not belong to this workspace."})

        assignee_ids = attrs.get("assignee_ids", self.instance.assignee_ids if self.instance else [])
        member_ids = {
            str(member_id)
            for member_id in ProjectMember.objects.filter(
                project_id=project_id,
                member_id__in=assignee_ids,
                is_active=True,
            ).values_list("member_id", flat=True)
        }
        invalid_assignees = {str(user_id) for user_id in assignee_ids} - member_ids
        if invalid_assignees:
            raise serializers.ValidationError(
                {"assignee_ids": f"Users are not active project members: {sorted(invalid_assignees)}"}
            )

        label_ids = attrs.get("label_ids", self.instance.label_ids if self.instance else [])
        valid_label_ids = {
            str(label_id)
            for label_id in Label.objects.filter(project_id=project_id, id__in=label_ids).values_list("id", flat=True)
        }
        invalid_labels = {str(label_id) for label_id in label_ids} - valid_label_ids
        if invalid_labels:
            raise serializers.ValidationError(
                {"label_ids": f"Labels do not belong to this project: {sorted(invalid_labels)}"}
            )
        return attrs
