# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.db.models import ProjectMember, State, WorkflowTransitionRule

VALID_ROLES = {20, 15, 5}


class WorkflowTransitionRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowTransitionRule
        fields = [
            "id",
            "from_state",
            "to_state",
            "allowed_roles",
            "approver_ids",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_allowed_roles(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("allowed_roles must be a list of role values (20, 15, 5).")
        roles = []
        for role in value:
            try:
                role = int(role)
            except (TypeError, ValueError):
                raise serializers.ValidationError(f"Invalid role {role!r}.")
            if role not in VALID_ROLES:
                raise serializers.ValidationError(f"Invalid role {role}. Use 20 (Admin), 15 (Member) or 5 (Guest).")
            if role not in roles:
                roles.append(role)
        return roles

    def validate_approver_ids(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("approver_ids must be a list of user ids.")
        return [str(uid) for uid in value]

    def validate(self, attrs):
        project_id = self.context["project_id"]
        instance = self.instance

        to_state = attrs.get("to_state", instance.to_state if instance else None)
        from_state = attrs.get("from_state", instance.from_state if instance else None)
        if to_state is None:
            raise serializers.ValidationError({"to_state": "Target state is required."})
        for label, state in (("to_state", to_state), ("from_state", from_state)):
            if state is not None and not State.objects.filter(pk=state.pk, project_id=project_id).exists():
                raise serializers.ValidationError({label: "State does not belong to this project."})
        if from_state is not None and from_state.pk == to_state.pk:
            raise serializers.ValidationError({"from_state": "Source and target state must differ."})

        approver_ids = attrs.get("approver_ids", instance.approver_ids if instance else [])
        if approver_ids:
            members = {
                str(m)
                for m in ProjectMember.objects.filter(
                    project_id=project_id, member_id__in=approver_ids, is_active=True
                ).values_list("member_id", flat=True)
            }
            unknown = sorted(set(approver_ids) - members)
            if unknown:
                raise serializers.ValidationError(
                    {"approver_ids": f"Users are not active project members: {unknown}"}
                )

        allowed_roles = attrs.get("allowed_roles", instance.allowed_roles if instance else [])
        if not allowed_roles and not approver_ids:
            raise serializers.ValidationError(
                "A rule needs at least one allowed role or one approver, otherwise nobody could ever use the transition."
            )

        duplicate = WorkflowTransitionRule.objects.filter(
            project_id=project_id, to_state=to_state, from_state=from_state
        )
        if instance:
            duplicate = duplicate.exclude(pk=instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError("A rule for this transition already exists.")
        return attrs
