from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers.customization import (
    ProjectCustomPropertySerializer,
    ProjectIssueTypeSerializer,
    WorkItemTemplateSerializer,
)
from plane.app.views.base import BaseAPIView
from plane.db.models import IssueType, Project, ProjectCustomProperty, ProjectIssueType, WorkItemTemplate


class ProjectCustomizationMixin(BaseAPIView):
    def project_queryset(self, model, slug, project_id):
        return model.objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            project__project_projectmember__member=self.request.user,
            project__project_projectmember__is_active=True,
        )


class ProjectCustomPropertyEndpoint(ProjectCustomizationMixin):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        queryset = self.project_queryset(ProjectCustomProperty, slug, project_id)
        return Response(ProjectCustomPropertySerializer(queryset, many=True).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id):
        serializer = ProjectCustomPropertySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        value = serializer.save(project_id=project_id)
        return Response(ProjectCustomPropertySerializer(value).data, status=status.HTTP_201_CREATED)


class ProjectCustomPropertyDetailEndpoint(ProjectCustomizationMixin):
    def get_property(self, slug, project_id, property_id):
        return self.project_queryset(ProjectCustomProperty, slug, project_id).get(pk=property_id)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def patch(self, request, slug, project_id, property_id):
        value = self.get_property(slug, project_id, property_id)
        serializer = ProjectCustomPropertySerializer(value, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(ProjectCustomPropertySerializer(serializer.save()).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def delete(self, request, slug, project_id, property_id):
        self.get_property(slug, project_id, property_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkItemTemplateEndpoint(ProjectCustomizationMixin):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        queryset = self.project_queryset(WorkItemTemplate, slug, project_id).filter(is_active=True)
        return Response(WorkItemTemplateSerializer(queryset, many=True).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id):
        serializer = WorkItemTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        value = serializer.save(project_id=project_id)
        return Response(WorkItemTemplateSerializer(value).data, status=status.HTTP_201_CREATED)


class WorkItemTemplateDetailEndpoint(ProjectCustomizationMixin):
    def get_template(self, slug, project_id, template_id):
        return self.project_queryset(WorkItemTemplate, slug, project_id).get(pk=template_id)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def patch(self, request, slug, project_id, template_id):
        value = self.get_template(slug, project_id, template_id)
        serializer = WorkItemTemplateSerializer(value, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(WorkItemTemplateSerializer(serializer.save()).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def delete(self, request, slug, project_id, template_id):
        self.get_template(slug, project_id, template_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectIssueTypeEndpoint(ProjectCustomizationMixin):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        if request.GET.get("available") == "true":
            if not project.project_projectmember.filter(member=request.user, is_active=True).exists():
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
            assigned_ids = ProjectIssueType.objects.filter(
                project=project, deleted_at__isnull=True
            ).values_list("issue_type_id", flat=True)
            return Response(
                list(
                    IssueType.objects.filter(
                        workspace=project.workspace, is_active=True
                    ).exclude(id__in=assigned_ids).values("id", "name", "description")
                )
            )
        queryset = ProjectIssueType.objects.filter(
            project__workspace__slug=slug,
            project_id=project_id,
            project__project_projectmember__member=request.user,
            project__project_projectmember__is_active=True,
            issue_type__is_active=True,
        ).select_related("issue_type")
        return Response(ProjectIssueTypeSerializer(queryset, many=True).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        serializer = ProjectIssueTypeSerializer(
            data=request.data,
            context={"project_id": project_id, "workspace_id": project.workspace_id},
        )
        serializer.is_valid(raise_exception=True)
        value = serializer.save(project_id=project_id)
        return Response(ProjectIssueTypeSerializer(value).data, status=status.HTTP_201_CREATED)


class ProjectIssueTypeDetailEndpoint(ProjectCustomizationMixin):
    def get_type(self, slug, project_id, type_id):
        return ProjectIssueType.objects.filter(
            project__workspace__slug=slug,
            project_id=project_id,
            project__project_projectmember__member=self.request.user,
            project__project_projectmember__is_active=True,
        ).get(pk=type_id)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def patch(self, request, slug, project_id, type_id):
        value = self.get_type(slug, project_id, type_id)
        serializer = ProjectIssueTypeSerializer(
            value,
            data=request.data,
            partial=True,
            context={"project_id": project_id, "workspace_id": value.project.workspace_id},
        )
        serializer.is_valid(raise_exception=True)
        return Response(ProjectIssueTypeSerializer(serializer.save()).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def delete(self, request, slug, project_id, type_id):
        self.get_type(slug, project_id, type_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
