# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.db.models import Dashboard, DashboardWidget
from plane.utils.dashboard import FILTER_KEYS

from .user import UserLiteSerializer


class DashboardWidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardWidget
        fields = [
            "id",
            "dashboard",
            "title",
            "chart_type",
            "metric",
            "group_by",
            "filters",
            "width",
            "height",
            "sort_order",
            "config",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "dashboard", "created_at", "updated_at"]

    def validate_filters(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("filters must be an object.")
        unknown = set(value) - set(FILTER_KEYS)
        if unknown:
            raise serializers.ValidationError(f"Unknown filter keys: {', '.join(sorted(unknown))}")
        return value

    def validate_width(self, value):
        if value not in (1, 2, 3):
            raise serializers.ValidationError("width must be 1, 2 or 3.")
        return value

    def validate_height(self, value):
        if value not in (1, 2):
            raise serializers.ValidationError("height must be 1 or 2.")
        return value

    def validate(self, attrs):
        chart = attrs.get("chart_type", getattr(self.instance, "chart_type", None))
        group_by = attrs.get("group_by", getattr(self.instance, "group_by", ""))
        if chart in (DashboardWidget.CHART_BAR, DashboardWidget.CHART_PIE, DashboardWidget.CHART_LINE) and not group_by:
            raise serializers.ValidationError({"group_by": "Bar, pie and line charts need a group_by."})
        return attrs


class DashboardSerializer(serializers.ModelSerializer):
    owner_detail = UserLiteSerializer(source="owner", read_only=True)
    widget_count = serializers.SerializerMethodField()

    class Meta:
        model = Dashboard
        fields = [
            "id",
            "workspace",
            "name",
            "description",
            "owner",
            "owner_detail",
            "project",
            "is_shared",
            "logo_props",
            "widget_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "workspace", "owner", "created_at", "updated_at"]

    def get_widget_count(self, obj):
        annotated = getattr(obj, "widget_count", None)
        return annotated if annotated is not None else obj.widgets.count()


class DashboardDetailSerializer(DashboardSerializer):
    widgets = DashboardWidgetSerializer(many=True, read_only=True)

    class Meta(DashboardSerializer.Meta):
        fields = DashboardSerializer.Meta.fields + ["widgets"]
