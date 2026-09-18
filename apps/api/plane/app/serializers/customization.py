from plane.utils.project_rbac_scope import ScopedPrimaryKeyRelatedField
from rest_framework import serializers

from plane.db.models import IssueType, ProjectCustomProperty, ProjectIssueType, WorkItemTemplate


class ProjectCustomPropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectCustomProperty
        fields = ["id", "name", "key", "property_type", "options", "is_required", "is_active"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        property_type = attrs.get("property_type", self.instance.property_type if self.instance else "text")
        options = attrs.get("options", self.instance.options if self.instance else [])
        if property_type in {"select", "multi_select"} and not isinstance(options, list):
            raise serializers.ValidationError({"options": "Select properties require a list of options."})
        if property_type not in {"select", "multi_select"} and options:
            raise serializers.ValidationError({"options": "Options are only valid for select properties."})
        return attrs


class WorkItemTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkItemTemplate
        fields = ["id", "name", "description", "defaults", "is_active"]
        read_only_fields = ["id"]


class ProjectIssueTypeSerializer(serializers.ModelSerializer):
    issue_type_id = ScopedPrimaryKeyRelatedField(source="issue_type", queryset=IssueType.objects.all(), write_only=True)
    name = serializers.CharField(source="issue_type.name", read_only=True)
    description = serializers.CharField(source="issue_type.description", read_only=True)

    class Meta:
        model = ProjectIssueType
        fields = ["id", "issue_type_id", "name", "description", "level", "is_default"]
        read_only_fields = ["id", "name", "description"]

    def validate_issue_type_id(self, issue_type):
        workspace_id = self.context.get("workspace_id")
        if workspace_id and issue_type.workspace_id != workspace_id:
            raise serializers.ValidationError("Work item type does not belong to this workspace.")
        project_id = self.context.get("project_id")
        assigned = ProjectIssueType.objects.filter(
            issue_type_id=issue_type.id,
            project_id=project_id,
            deleted_at__isnull=True,
        )
        if self.instance:
            assigned = assigned.exclude(pk=self.instance.pk)
        if project_id and assigned.exists():
            raise serializers.ValidationError("This work item type is already assigned to the project.")
        return issue_type
