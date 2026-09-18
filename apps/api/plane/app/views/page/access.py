"""Authorize each live-editor connection, including already-cached documents."""

from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from plane.app.views.base import BaseAPIView
from plane.db.models import Page, ProjectMember, ProjectPage
from plane.app.permissions.page import ProjectPagePermission
from plane.utils.project_rbac import require_project_capability


class PageAccessEndpoint(BaseAPIView):
    permission_classes = [ProjectPagePermission]
    rbac_policy = {"GET": "pages.read"}

    def get(self, request, slug, project_id, page_id):
        page = Page.objects.get(pk=page_id, workspace__slug=slug, projects__id=project_id)
        if request.query_params.get("action") == "export":
            require_project_capability(request, project_id, "pages.export")
        role = (
            ProjectMember.objects.filter(project_id=project_id, member=request.user, is_active=True)
            .values_list("role", flat=True)
            .first()
        )
        can_edit = bool(
            not page.is_locked and not page.archived_at and (page.owned_by_id == request.user.id or role in (15, 20))
        )
        try:
            for affected_project in ProjectPage.objects.filter(page=page).values_list("project_id", flat=True):
                require_project_capability(request, affected_project, "pages.update")
        except PermissionDenied:
            can_edit = False
        return Response({"can_edit": can_edit})
