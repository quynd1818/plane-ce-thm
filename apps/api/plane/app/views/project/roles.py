"""Administration and a deliberately small API surface for restricted roles."""

import json
import math
from datetime import date

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers.customization import ProjectCustomPropertySerializer
from plane.app.views.base import BaseAPIView
from plane.db.models import (
    Issue,
    IssueActivity,
    Project,
    ProjectCustomProperty,
    ProjectCustomRole,
    ProjectMember,
    ProjectRoleAssignment,
    WorkspaceMember,
)
from plane.utils.project_rbac import CAPABILITIES, assignments_for


class CustomRoleSerializer(serializers.ModelSerializer):
    permissions = serializers.ListField(child=serializers.ChoiceField(choices=list(CAPABILITIES)), allow_empty=True)
    property_keys = serializers.ListField(child=serializers.SlugField(max_length=100), required=False)

    class Meta:
        model = ProjectCustomRole
        fields = ["id", "name", "permissions", "property_keys", "is_active"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        permissions = set(attrs.get("permissions", self.instance.permissions if self.instance else []))
        keys = set(attrs.get("property_keys", self.instance.property_keys if self.instance else []))
        if "worklogs.export" in permissions and "worklogs.read" not in permissions:
            raise serializers.ValidationError("Export requires worklogs.read.")
        if "properties.edit" in permissions and ("issues.read" not in permissions or not keys):
            raise serializers.ValidationError("Property editing requires issues.read and at least one property key.")
        if keys and "properties.edit" not in permissions:
            raise serializers.ValidationError("Property keys require properties.edit.")
        valid_keys = set(
            ProjectCustomProperty.objects.filter(
                project_id=self.context["project_id"],
                is_active=True,
            ).values_list("key", flat=True)
        )
        if attrs.get("is_active", self.instance.is_active if self.instance else True) and keys - valid_keys:
            raise serializers.ValidationError({"property_keys": "Select active properties from this project."})
        attrs["permissions"] = sorted(permissions)
        attrs["property_keys"] = sorted(keys)
        return attrs


class ProjectCustomRoleEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN])
    def get(self, request, slug, project_id):
        roles = ProjectCustomRole.objects.filter(project_id=project_id, workspace__slug=slug).order_by("name")
        memberships = ProjectMember.all_objects.filter(project_id=project_id).select_related("member")
        assignments = {
            str(a.membership_id): str(a.custom_role_id)
            for a in ProjectRoleAssignment.all_objects.filter(project_id=project_id)
        }
        workspace_admins = set(
            WorkspaceMember.objects.filter(workspace__slug=slug, role=20, is_active=True).values_list(
                "member_id", flat=True
            )
        )
        return Response(
            {
                "roles": CustomRoleSerializer(roles, many=True).data,
                "capabilities": CAPABILITIES,
                "members": [
                    {
                        "id": str(m.id),
                        "name": m.member.display_name or m.member.email,
                        "eligible": m.is_active
                        and m.deleted_at is None
                        and m.role == 15
                        and m.member_id not in workspace_admins,
                        "custom_role_id": assignments.get(str(m.id)),
                    }
                    for m in memberships
                    if m.member
                ],
            }
        )

    @allow_permission([ROLE.ADMIN])
    def post(self, request, slug, project_id):
        project = get_object_or_404(Project, pk=project_id, workspace__slug=slug)
        serializer = CustomRoleSerializer(data=request.data, context={"project_id": project_id})
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project)
        return Response(serializer.data, status=201)


class ProjectCustomRoleDetailEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN])
    @transaction.atomic
    def patch(self, request, slug, project_id, role_id):
        role = get_object_or_404(
            ProjectCustomRole.objects.select_for_update(), pk=role_id, project_id=project_id, workspace__slug=slug
        )
        serializer = CustomRoleSerializer(role, data=request.data, partial=True, context={"project_id": project_id})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @allow_permission([ROLE.ADMIN])
    @transaction.atomic
    def delete(self, request, slug, project_id, role_id):
        role = get_object_or_404(
            ProjectCustomRole.objects.select_for_update(), pk=role_id, project_id=project_id, workspace__slug=slug
        )
        # Do not silently restore broader Member permissions on deletion.
        if ProjectRoleAssignment.all_objects.filter(custom_role=role).exists():
            return Response({"error": "Remove all assignments before deleting this role, or disable it."}, status=409)
        ProjectCustomRole.objects.filter(pk=role.pk).delete()
        return Response(status=204)


class RoleAssignmentInput(serializers.Serializer):
    custom_role_id = serializers.UUIDField(allow_null=True)


class ProjectRoleAssignmentEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN])
    @transaction.atomic
    def put(self, request, slug, project_id, membership_id):
        serializer = RoleAssignmentInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        role_id = serializer.validated_data["custom_role_id"]
        role = None
        if role_id:
            role = get_object_or_404(
                ProjectCustomRole.objects.select_for_update(),
                pk=role_id,
                project_id=project_id,
                workspace__slug=slug,
                is_active=True,
            )
        member = get_object_or_404(
            ProjectMember.all_objects.select_for_update(),
            pk=membership_id,
            project_id=project_id,
            workspace__slug=slug,
        )
        if role is None:
            # Hard-delete the assignment; the OneToOne key must be reusable.
            ProjectRoleAssignment.all_objects.filter(membership=member).delete()
            return Response({"custom_role_id": None})
        if (
            not member.is_active
            or member.deleted_at is not None
            or member.role != 15
            or not WorkspaceMember.objects.filter(
                workspace_id=member.workspace_id, member_id=member.member_id, role=15, is_active=True
            ).exists()
        ):
            raise ValidationError(
                "Custom roles can only restrict active Members. Admin and Guest roles cannot be assigned."
            )
        assignment, _ = ProjectRoleAssignment.all_objects.update_or_create(
            membership=member,
            defaults={
                "project_id": project_id,
                "workspace_id": member.workspace_id,
                "custom_role": role,
                "deleted_at": None,
            },
        )
        return Response({"custom_role_id": str(assignment.custom_role_id)})


class ProjectRoleMeEndpoint(BaseAPIView):
    rbac_policy = {"GET": "metadata"}

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        assignment = assignments_for(request.user).filter(project_id=project_id, workspace__slug=slug).first()
        if not assignment:
            return Response({"restricted": False, "role": None})
        role = assignment.custom_role
        active = role.is_active and role.deleted_at is None and role.project_id == assignment.project_id
        return Response(
            {
                "restricted": True,
                "role": {
                    "id": str(role.id),
                    "name": role.name,
                    "is_active": active,
                    "permissions": role.permissions if active else [],
                    "property_keys": role.property_keys if active else [],
                },
            }
        )


class RoleIssueEndpoint(BaseAPIView):
    rbac_policy = {"GET": "issues.read"}

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def get(self, request, slug, project_id):
        # No descriptions, attachments or related-project information is exposed.
        query = request.query_params.get("search", "")[:200]
        try:
            offset = max(0, int(request.query_params.get("offset", 0)))
        except ValueError:
            raise ValidationError({"offset": "Expected an integer."})
        issues = Issue.issue_objects.filter(
            project_id=project_id, workspace__slug=slug, name__icontains=query
        ).order_by("sequence_id")
        return Response(
            {
                "count": issues.count(),
                "results": list(issues.values("id", "name", "sequence_id", "custom_properties")[offset : offset + 50]),
                "properties": ProjectCustomPropertySerializer(
                    ProjectCustomProperty.objects.filter(project_id=project_id, is_active=True), many=True
                ).data,
            }
        )


class RoleIssueDetailEndpoint(BaseAPIView):
    rbac_policy = {"PATCH": "properties.edit"}

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    @transaction.atomic
    def patch(self, request, slug, project_id, issue_id):
        if not isinstance(request.data, dict) or set(request.data) != {"custom_properties"}:
            raise ValidationError("Only custom_properties may be changed here.")
        changes = request.data["custom_properties"]
        if not isinstance(changes, dict) or not changes:
            raise ValidationError("Provide a non-empty custom_properties object.")
        # Lock the role so an edit cannot race a role revocation.
        assignment = assignments_for(request.user).filter(project_id=project_id).first()
        if assignment:
            role = ProjectCustomRole.objects.select_for_update().get(pk=assignment.custom_role_id)
            # Lock in the same order as administration: role, then assignment.
            current_assignment = (
                ProjectRoleAssignment.all_objects.select_for_update(of=("self",))
                .filter(
                    pk=assignment.pk,
                    custom_role=role,
                    membership__is_active=True,
                    membership__deleted_at__isnull=True,
                )
                .first()
            )
            if current_assignment is None:
                raise PermissionDenied("Your role assignment changed. Reload and try again.")
            if (
                not role.is_active
                or "properties.edit" not in role.permissions
                or set(changes) - set(role.property_keys)
            ):
                raise PermissionDenied("You may only edit the custom properties granted by your role.")
        definitions = {p.key: p for p in ProjectCustomProperty.objects.filter(project_id=project_id, is_active=True)}
        for key, value in changes.items():
            prop = definitions.get(key)
            if prop is None:
                raise ValidationError({key: "Unknown or inactive property."})
            valid = True
            if value is None:
                valid = not prop.is_required
            elif prop.property_type in {"text", "date", "select"}:
                valid = isinstance(value, str) and (not prop.is_required or bool(value.strip()))
                if valid and prop.property_type == "select":
                    valid = value in prop.options
                if valid and prop.property_type == "date":
                    try:
                        date.fromisoformat(value)
                    except ValueError:
                        valid = False
            elif prop.property_type == "number":
                valid = type(value) is int or (type(value) is float and math.isfinite(value))
            elif prop.property_type == "boolean":
                valid = isinstance(value, bool)
            elif prop.property_type == "multi_select":
                valid = (
                    isinstance(value, list)
                    and all(isinstance(v, str) and v in prop.options for v in value)
                    and (not prop.is_required or bool(value))
                )
            if not valid:
                raise ValidationError({key: "Invalid value for this property."})
        issue = get_object_or_404(
            Issue.issue_objects.select_for_update(of=("self",)),
            pk=issue_id,
            project_id=project_id,
            workspace__slug=slug,
        )
        old = issue.custom_properties or {}
        issue.custom_properties = {**old, **changes}
        issue.save(update_fields=["custom_properties", "updated_at", "updated_by"])
        IssueActivity.objects.create(
            project_id=project_id,
            workspace_id=issue.workspace_id,
            issue=issue,
            actor=request.user,
            verb="updated",
            field="custom_properties",
            old_value=json.dumps({k: old.get(k) for k in changes}),
            new_value=json.dumps(changes),
            comment="Updated custom properties",
        )
        return Response({"id": str(issue.id), "custom_properties": issue.custom_properties})


class WorkspaceRoleAccessEndpoint(BaseAPIView):
    rbac_policy = {"GET": "metadata"}

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug):
        assignments = {a.project_id: a for a in assignments_for(request.user).filter(workspace__slug=slug)}
        if not assignments:
            return Response({"restricted": False, "projects": []})
        projects = Project.objects.filter(
            workspace__slug=slug,
            project_projectmember__member=request.user,
            project_projectmember__is_active=True,
            project_projectmember__deleted_at__isnull=True,
        ).order_by("name")
        result = []
        for project in projects:
            assignment = assignments.get(project.id)
            role_data = None
            if assignment:
                role = assignment.custom_role
                active = role.is_active and role.deleted_at is None and role.project_id == project.id
                role_data = {
                    "id": str(role.id),
                    "name": role.name,
                    "is_active": active,
                    "permissions": role.permissions if active else [],
                    "property_keys": role.property_keys if active else [],
                }
            result.append({"id": str(project.id), "name": project.name, "role": role_data})
        return Response({"restricted": True, "projects": result})
