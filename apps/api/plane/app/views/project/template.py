# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""THM project templates.

* ``/workspaces/<slug>/project-templates/``            list / create (raw JSON)
* ``/workspaces/<slug>/project-templates/<id>/``       retrieve / patch / delete
* ``/workspaces/<slug>/projects/<id>/save-as-template/`` snapshot an existing project

Applying a template happens inside project creation: ``POST /projects/`` with
``template_id`` (see ``ProjectViewSet.create``).
"""

from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import ProjectTemplateLiteSerializer, ProjectTemplateSerializer
from plane.app.views.base import BaseAPIView
from plane.db.models import Project, ProjectTemplate, Workspace, WorkspaceMember
from plane.utils.project_template import capture_project


def _name_taken(slug, name, exclude_id=None) -> bool:
    qs = ProjectTemplate.objects.filter(workspace__slug=slug, name=name)
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


NAME_TAKEN = {"name": ["A template with this name already exists in the workspace."]}


def _can_manage(template, user, slug) -> bool:
    """Owner, or a workspace admin."""
    if template.owner_id == user.id:
        return True
    return WorkspaceMember.objects.filter(
        workspace__slug=slug, member=user, role=ROLE.ADMIN.value, is_active=True
    ).exists()


class ProjectTemplateEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug):
        templates = ProjectTemplate.objects.filter(workspace__slug=slug).select_related("owner")
        if request.GET.get("lite") == "true":
            return Response(ProjectTemplateLiteSerializer(templates, many=True).data)
        return Response(ProjectTemplateSerializer(templates, many=True).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        serializer = ProjectTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if _name_taken(slug, serializer.validated_data["name"]):
            return Response(NAME_TAKEN, status=status.HTTP_409_CONFLICT)
        template = serializer.save(workspace=workspace, owner=request.user)
        return Response(ProjectTemplateSerializer(template).data, status=status.HTTP_201_CREATED)


class ProjectTemplateDetailEndpoint(BaseAPIView):
    def _get(self, slug, template_id):
        return ProjectTemplate.objects.filter(workspace__slug=slug, pk=template_id).select_related("owner").first()

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug, template_id):
        template = self._get(slug, template_id)
        if template is None:
            return Response({"error": "Template not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProjectTemplateSerializer(template).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def patch(self, request, slug, template_id):
        template = self._get(slug, template_id)
        if template is None:
            return Response({"error": "Template not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_manage(template, request.user, slug):
            return Response(
                {"error": "Only the template owner or a workspace admin can edit it."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = ProjectTemplateSerializer(template, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        new_name = serializer.validated_data.get("name")
        if new_name and _name_taken(slug, new_name, exclude_id=template.id):
            return Response(NAME_TAKEN, status=status.HTTP_409_CONFLICT)
        serializer.save()
        return Response(serializer.data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def delete(self, request, slug, template_id):
        template = self._get(slug, template_id)
        if template is None:
            return Response({"error": "Template not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_manage(template, request.user, slug):
            return Response(
                {"error": "Only the template owner or a workspace admin can delete it."},
                status=status.HTTP_403_FORBIDDEN,
            )
        template.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectSaveAsTemplateEndpoint(BaseAPIView):
    """Snapshot a project the caller administers into a new template."""

    @allow_permission([ROLE.ADMIN])
    def post(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"name": ["Template name is required."]}, status=status.HTTP_400_BAD_REQUEST)
        include_work_items = str(request.data.get("include_work_items", "false")).lower() in ("1", "true", "yes")
        if _name_taken(slug, name[:255]):
            return Response(NAME_TAKEN, status=status.HTTP_409_CONFLICT)
        template = ProjectTemplate.objects.create(
            workspace=project.workspace,
            name=name[:255],
            description=request.data.get("description") or "",
            template_data=capture_project(project, include_work_items=include_work_items),
            source_project=project,
            owner=request.user,
        )
        return Response(ProjectTemplateSerializer(template).data, status=status.HTTP_201_CREATED)
