# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.db.models import Initiative

from .user import UserLiteSerializer


class InitiativeSerializer(serializers.ModelSerializer):
    lead_detail = UserLiteSerializer(source="lead", read_only=True)
    project_ids = serializers.SerializerMethodField()
    epic_ids = serializers.SerializerMethodField()

    class Meta:
        model = Initiative
        fields = [
            "id",
            "workspace",
            "name",
            "description_html",
            "status",
            "lead",
            "lead_detail",
            "start_date",
            "end_date",
            "logo_props",
            "sort_order",
            "project_ids",
            "epic_ids",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "workspace", "created_by", "created_at", "updated_at"]

    def get_project_ids(self, obj):
        links = getattr(obj, "_project_links", None)
        if links is None:
            links = obj.initiative_projects.filter(deleted_at__isnull=True)
        return [str(link.project_id) for link in links]

    def get_epic_ids(self, obj):
        links = getattr(obj, "_epic_links", None)
        if links is None:
            links = obj.initiative_epics.filter(deleted_at__isnull=True)
        return [str(link.epic_id) for link in links]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and start > end:
            raise serializers.ValidationError({"end_date": "End date cannot be before start date."})
        return attrs
