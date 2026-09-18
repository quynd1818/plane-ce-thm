from plane.utils.project_rbac_scope import ScopedPrimaryKeyRelatedField
from rest_framework import serializers

from plane.db.models import Issue, WorkLog
from .user import UserLiteSerializer




class WorkLogSerializer(serializers.ModelSerializer):
    user_detail = UserLiteSerializer(source="user", read_only=True)
    reviewed_by_detail = UserLiteSerializer(source="reviewed_by", read_only=True)

    class Meta:
        model = WorkLog
        fields = [
            "id",
            "issue",
            "user",
            "user_detail",
            "description",
            "duration_seconds",
            "started_at",
            "ended_at",
            "is_timer",
            "status",
            "reviewed_by",
            "reviewed_by_detail",
            "reviewed_at",
            "review_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "issue",
            "user",
            "user_detail",
            "is_timer",
            "status",
            "reviewed_by",
            "reviewed_by_detail",
            "reviewed_at",
            "review_note",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        issue = self.instance.issue if self.instance else self.context["issue"]
        if issue.project.is_time_tracking_enabled is not True:
            raise serializers.ValidationError("Time tracking is disabled for this project.")
        if self.instance and self.instance.is_timer and self.instance.ended_at is None:
            raise serializers.ValidationError("Active timers must be stopped before they can be edited.")

        started_at = attrs.get("started_at", self.instance.started_at if self.instance else None)
        ended_at = attrs.get("ended_at", self.instance.ended_at if self.instance else None)
        if ended_at and started_at and ended_at < started_at:
            raise serializers.ValidationError({"ended_at": "End time cannot be before start time."})
        if attrs.get("duration_seconds", self.instance.duration_seconds if self.instance else 0) < 1:
            raise serializers.ValidationError({"duration_seconds": "Duration must be greater than zero."})
        return attrs


class WorkLogCreateSerializer(WorkLogSerializer):
    issue = ScopedPrimaryKeyRelatedField(queryset=Issue.objects.all(), write_only=True)

    def validate_issue(self, issue):
        project_id = self.context["project_id"]
        if issue.project_id != project_id:
            raise serializers.ValidationError("Issue does not belong to this project.")
        return issue
