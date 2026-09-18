# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.db.models import ProjectTemplate
from plane.utils.project_template import PROJECT_SETTING_FIELDS

from .user import UserLiteSerializer

TEMPLATE_LIST_KEYS = (
    "states",
    "labels",
    "modules",
    "workflow_rules",
    "custom_properties",
    "work_item_templates",
    "work_items",
)


class ProjectTemplateSerializer(serializers.ModelSerializer):
    owner_detail = UserLiteSerializer(source="owner", read_only=True)
    summary = serializers.SerializerMethodField()

    class Meta:
        model = ProjectTemplate
        fields = [
            "id",
            "workspace",
            "name",
            "description",
            "template_data",
            "source_project",
            "owner",
            "owner_detail",
            "usage_count",
            "summary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "workspace", "source_project", "owner", "usage_count", "created_at", "updated_at"]

    def get_summary(self, obj):
        data = obj.template_data or {}
        return {key: len(data.get(key) or []) for key in TEMPLATE_LIST_KEYS}

    def validate_template_data(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("template_data must be an object.")
        for key in TEMPLATE_LIST_KEYS:
            if key in value and not isinstance(value[key], list):
                raise serializers.ValidationError({key: "must be a list."})
        project = value.get("project")
        if project is not None:
            if not isinstance(project, dict):
                raise serializers.ValidationError({"project": "must be an object."})
            unknown = set(project) - set(PROJECT_SETTING_FIELDS)
            if unknown:
                raise serializers.ValidationError({"project": f"unknown settings: {', '.join(sorted(unknown))}"})
        for s in value.get("states") or []:
            if not isinstance(s, dict) or not s.get("name"):
                raise serializers.ValidationError({"states": "every state needs a name."})
        return value


class ProjectTemplateLiteSerializer(serializers.ModelSerializer):
    """For pickers: no template_data payload."""

    summary = serializers.SerializerMethodField()

    class Meta:
        model = ProjectTemplate
        fields = ["id", "name", "description", "usage_count", "summary"]
        read_only_fields = fields

    def get_summary(self, obj):
        data = obj.template_data or {}
        return {key: len(data.get(key) or []) for key in TEMPLATE_LIST_KEYS}
