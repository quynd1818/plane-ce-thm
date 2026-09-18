# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""THM custom dashboards.

* ``/workspaces/<slug>/dashboards/``                          list / create
* ``/workspaces/<slug>/dashboards/<id>/``                     retrieve (with widgets) / patch / delete
* ``/workspaces/<slug>/dashboards/<id>/widgets/``             create
* ``/workspaces/<slug>/dashboards/<id>/widgets/reorder/``     bulk order + size
* ``/workspaces/<slug>/dashboards/<id>/widgets/<wid>/``       patch / delete
* ``/workspaces/<slug>/dashboards/<id>/widgets/<wid>/data/``  computed data for the viewer
* ``/workspaces/<slug>/dashboards/<id>/data/``                computed data for every widget

Visibility: a shared dashboard is visible to every workspace member; a
private one only to its owner. Editing is owner or workspace admin. Data is
always computed against the projects the *viewer* belongs to.
"""

from django.db.models import Count, Q
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import DashboardDetailSerializer, DashboardSerializer, DashboardWidgetSerializer
from plane.app.views.base import BaseAPIView
from plane.db.models import Dashboard, DashboardWidget, Workspace, WorkspaceMember
from plane.utils.dashboard import compute_widget


from plane.utils.project_rbac_scope import scoped_queryset


def _visible(slug, user):
    return (
        scoped_queryset(Dashboard.objects.all())
        .filter(workspace__slug=slug)
        .filter(Q(is_shared=True) | Q(owner=user))
        .select_related("owner")
        .annotate(widget_count=Count("widgets", filter=Q(widgets__deleted_at__isnull=True)))
    )


def _can_edit(dashboard, user, slug) -> bool:
    if dashboard.owner_id == user.id:
        return True
    return WorkspaceMember.objects.filter(
        workspace__slug=slug, member=user, role=ROLE.ADMIN.value, is_active=True
    ).exists()


FORBIDDEN = {"error": "Only the dashboard owner or a workspace admin can change it."}
NOT_FOUND = {"error": "Dashboard not found."}


class DashboardEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug):
        return Response(DashboardSerializer(_visible(slug, request.user), many=True).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        serializer = DashboardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = serializer.validated_data.get("project")
        if project is not None and project.workspace_id != workspace.id:
            return Response({"project": ["Project is not in this workspace."]}, status=status.HTTP_400_BAD_REQUEST)
        dashboard = serializer.save(workspace=workspace, owner=request.user)
        return Response(DashboardSerializer(dashboard).data, status=status.HTTP_201_CREATED)


class DashboardDetailEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug, dashboard_id):
        dashboard = _visible(slug, request.user).prefetch_related("widgets").filter(pk=dashboard_id).first()
        if dashboard is None:
            return Response(NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        data = DashboardDetailSerializer(dashboard).data
        data["can_edit"] = _can_edit(dashboard, request.user, slug)
        return Response(data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def patch(self, request, slug, dashboard_id):
        dashboard = _visible(slug, request.user).filter(pk=dashboard_id).first()
        if dashboard is None:
            return Response(NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        if not _can_edit(dashboard, request.user, slug):
            return Response(FORBIDDEN, status=status.HTTP_403_FORBIDDEN)
        serializer = DashboardSerializer(dashboard, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        project = serializer.validated_data.get("project")
        if project is not None and project.workspace_id != dashboard.workspace_id:
            return Response({"project": ["Project is not in this workspace."]}, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def delete(self, request, slug, dashboard_id):
        dashboard = _visible(slug, request.user).filter(pk=dashboard_id).first()
        if dashboard is None:
            return Response(NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        if not _can_edit(dashboard, request.user, slug):
            return Response(FORBIDDEN, status=status.HTTP_403_FORBIDDEN)
        dashboard.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardWidgetEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug, dashboard_id):
        dashboard = _visible(slug, request.user).filter(pk=dashboard_id).first()
        if dashboard is None:
            return Response(NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        if not _can_edit(dashboard, request.user, slug):
            return Response(FORBIDDEN, status=status.HTTP_403_FORBIDDEN)
        serializer = DashboardWidgetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if "sort_order" not in request.data:
            last = DashboardWidget.objects.filter(dashboard=dashboard).order_by("-sort_order").first()
            serializer.validated_data["sort_order"] = (last.sort_order + 10000) if last else 65535
        widget = serializer.save(dashboard=dashboard)
        return Response(DashboardWidgetSerializer(widget).data, status=status.HTTP_201_CREATED)


class DashboardWidgetReorderEndpoint(BaseAPIView):
    """``{"widgets": [{"id", "sort_order", "width"?, "height"?}, ...]}``"""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug, dashboard_id):
        dashboard = _visible(slug, request.user).filter(pk=dashboard_id).first()
        if dashboard is None:
            return Response(NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        if not _can_edit(dashboard, request.user, slug):
            return Response(FORBIDDEN, status=status.HTTP_403_FORBIDDEN)
        items = request.data.get("widgets") or []
        by_id = {str(w.id): w for w in DashboardWidget.objects.filter(dashboard=dashboard)}
        for item in items:
            widget = by_id.get(str(item.get("id")))
            if widget is None:
                continue
            for field in ("sort_order", "width", "height"):
                if field in item:
                    setattr(widget, field, item[field])
            if widget.width not in (1, 2, 3) or widget.height not in (1, 2):
                return Response({"error": "width must be 1-3 and height 1-2."}, status=status.HTTP_400_BAD_REQUEST)
        DashboardWidget.objects.bulk_update(by_id.values(), ["sort_order", "width", "height"])
        widgets = DashboardWidget.objects.filter(dashboard=dashboard)
        return Response(DashboardWidgetSerializer(widgets, many=True).data)


class DashboardWidgetDetailEndpoint(BaseAPIView):
    def _get(self, slug, user, dashboard_id, widget_id):
        dashboard = _visible(slug, user).filter(pk=dashboard_id).first()
        if dashboard is None:
            return None, None
        return dashboard, DashboardWidget.objects.filter(dashboard=dashboard, pk=widget_id).first()

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def patch(self, request, slug, dashboard_id, widget_id):
        dashboard, widget = self._get(slug, request.user, dashboard_id, widget_id)
        if widget is None:
            return Response({"error": "Widget not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_edit(dashboard, request.user, slug):
            return Response(FORBIDDEN, status=status.HTTP_403_FORBIDDEN)
        serializer = DashboardWidgetSerializer(widget, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def delete(self, request, slug, dashboard_id, widget_id):
        dashboard, widget = self._get(slug, request.user, dashboard_id, widget_id)
        if widget is None:
            return Response({"error": "Widget not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_edit(dashboard, request.user, slug):
            return Response(FORBIDDEN, status=status.HTTP_403_FORBIDDEN)
        widget.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardWidgetDataEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug, dashboard_id, widget_id):
        dashboard = _visible(slug, request.user).filter(pk=dashboard_id).first()
        widget = (
            DashboardWidget.objects.filter(dashboard=dashboard, pk=widget_id).select_related("dashboard").first()
            if dashboard
            else None
        )
        if widget is None:
            return Response({"error": "Widget not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(compute_widget(widget, dashboard.workspace_id, request.user))


class DashboardDataEndpoint(BaseAPIView):
    """All widgets of a dashboard in one round-trip: ``{"<widget_id>": {...}}``."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug, dashboard_id):
        dashboard = _visible(slug, request.user).filter(pk=dashboard_id).first()
        if dashboard is None:
            return Response(NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        widgets = DashboardWidget.objects.filter(dashboard=dashboard).select_related("dashboard")
        return Response({str(w.id): compute_widget(w, dashboard.workspace_id, request.user) for w in widgets})
