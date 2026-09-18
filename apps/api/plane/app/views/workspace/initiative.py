# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""THM initiatives (workspace level).

* ``GET/POST   /workspaces/<slug>/initiatives/``
* ``GET/PATCH/DELETE /workspaces/<slug>/initiatives/<id>/``
* ``POST/DELETE /workspaces/<slug>/initiatives/<id>/projects/``  {project_ids}
* ``POST/DELETE /workspaces/<slug>/initiatives/<id>/epics/``     {epic_ids}
* ``GET        /workspaces/<slug>/initiatives/<id>/analytics/``  progress rollup
* ``GET        /workspaces/<slug>/epics/``                       all epics the viewer can see

Every workspace member can view initiatives; admins and members create;
the creator, the lead or a workspace admin edit / delete. Rollups only count
work items in projects the viewer belongs to.
"""

from django.db.models import Prefetch, Q
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import InitiativeSerializer
from plane.app.views.base import BaseAPIView
from plane.app.views.project.epic import _serialize_epics
from plane.db.models import Initiative, InitiativeEpic, InitiativeProject, Issue, Project, Workspace, WorkspaceMember
from plane.utils.dashboard import visible_project_ids
from plane.utils.epic import epic_queryset, rollup_for_queryset, visible_issues

from plane.utils.project_rbac_scope import scoped_queryset


NOT_FOUND = {"error": "Initiative not found."}
FORBIDDEN = {"error": "Only the initiative lead, its creator or a workspace admin can change it."}


def _queryset(slug):
    return (
        Initiative.objects.filter(workspace__slug=slug)
        .select_related("lead")
        .prefetch_related(
            Prefetch(
                "initiative_projects",
                queryset=scoped_queryset(InitiativeProject.objects.all())
                .filter(deleted_at__isnull=True)
                .order_by("sort_order"),
                to_attr="_project_links",
            ),
            Prefetch(
                "initiative_epics",
                queryset=scoped_queryset(InitiativeEpic.objects.all())
                .filter(deleted_at__isnull=True)
                .order_by("sort_order"),
                to_attr="_epic_links",
            ),
        )
    )


def _can_edit(initiative, user, slug) -> bool:
    if initiative.created_by_id == user.id or initiative.lead_id == user.id:
        return True
    return WorkspaceMember.objects.filter(
        workspace__slug=slug, member=user, role=ROLE.ADMIN.value, is_active=True
    ).exists()


def _rollup(initiative, user):
    """Work items in the linked projects plus the children of linked epics
    (epics outside those projects), limited to what the viewer can see."""
    visible = set(visible_project_ids(initiative.workspace_id, user))
    project_ids = [link.project_id for link in initiative._project_links if link.project_id in visible]
    epic_ids = [link.epic_id for link in initiative._epic_links]
    qs = (
        scoped_queryset(Issue.issue_objects.all())
        .filter(workspace_id=initiative.workspace_id)
        .filter(Q(project_id__in=project_ids) | Q(parent_id__in=epic_ids, project_id__in=list(visible)))
    )
    # epics themselves are containers, not work
    qs = qs.exclude(type__is_epic=True)
    data = rollup_for_queryset(visible_issues(qs, user))
    data["project_count"] = len(project_ids)
    data["epic_count"] = visible_issues(epic_queryset().filter(pk__in=epic_ids), user).count()
    return data


class InitiativeEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug):
        initiatives = _queryset(slug)
        data = InitiativeSerializer(initiatives, many=True).data
        if request.GET.get("analytics") == "true":
            by_id = {str(i.id): i for i in initiatives}
            for row in data:
                row["analytics"] = _rollup(by_id[row["id"]], request.user)
        return Response(data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        serializer = InitiativeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        initiative = serializer.save(workspace=workspace)
        return Response(
            InitiativeSerializer(_queryset(slug).get(pk=initiative.pk)).data, status=status.HTTP_201_CREATED
        )


class InitiativeDetailEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug, initiative_id):
        initiative = _queryset(slug).filter(pk=initiative_id).first()
        if initiative is None:
            return Response(NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        data = InitiativeSerializer(initiative).data
        data["analytics"] = _rollup(initiative, request.user)
        data["can_edit"] = _can_edit(initiative, request.user, slug)
        visible = set(visible_project_ids(initiative.workspace_id, request.user))
        data["projects"] = list(
            Project.objects.filter(pk__in=[link.project_id for link in initiative._project_links]).values(
                "id", "name", "identifier", "logo_props", "archived_at"
            )
        )
        for p in data["projects"]:
            p["is_member"] = p["id"] in visible
        epic_ids = [link.epic_id for link in initiative._epic_links]
        data["epics"] = _serialize_epics(
            epic_queryset(workspace_id=initiative.workspace_id).filter(pk__in=epic_ids, project_id__in=list(visible)),
            request.user,
        )
        return Response(data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def patch(self, request, slug, initiative_id):
        initiative = _queryset(slug).filter(pk=initiative_id).first()
        if initiative is None:
            return Response(NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        if not _can_edit(initiative, request.user, slug):
            return Response(FORBIDDEN, status=status.HTTP_403_FORBIDDEN)
        serializer = InitiativeSerializer(initiative, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(InitiativeSerializer(_queryset(slug).get(pk=initiative.pk)).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def delete(self, request, slug, initiative_id):
        initiative = _queryset(slug).filter(pk=initiative_id).first()
        if initiative is None:
            return Response(NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        if not _can_edit(initiative, request.user, slug):
            return Response(FORBIDDEN, status=status.HTTP_403_FORBIDDEN)
        initiative.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class _LinkEndpoint(BaseAPIView):
    key = ""  # "project_ids" | "epic_ids"

    def _initiative(self, slug, initiative_id, user):
        initiative = _queryset(slug).filter(pk=initiative_id).first()
        if initiative is None:
            return None, Response(NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        if not _can_edit(initiative, user, slug):
            return None, Response(FORBIDDEN, status=status.HTTP_403_FORBIDDEN)
        return initiative, None

    def _ids(self, request):
        return [str(i) for i in request.data.get(self.key) or []]

    def _done(self, slug, initiative):
        return Response(InitiativeSerializer(_queryset(slug).get(pk=initiative.pk)).data)


class InitiativeProjectsEndpoint(_LinkEndpoint):
    key = "project_ids"

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug, initiative_id):
        initiative, err = self._initiative(slug, initiative_id, request.user)
        if err:
            return err
        ids = self._ids(request)
        valid = set(
            str(i)
            for i in Project.objects.filter(pk__in=ids, workspace=initiative.workspace).values_list("id", flat=True)
        )
        if set(ids) - valid:
            return Response(
                {self.key: ["Some projects are not in this workspace."]}, status=status.HTTP_400_BAD_REQUEST
            )
        existing = set(str(link.project_id) for link in initiative._project_links)
        for i, pid in enumerate(ids):
            if pid not in existing:
                scoped_queryset(InitiativeProject.objects.all()).create(
                    initiative=initiative, project_id=pid, sort_order=(len(existing) + i + 1) * 10000
                )
        return self._done(slug, initiative)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def delete(self, request, slug, initiative_id):
        initiative, err = self._initiative(slug, initiative_id, request.user)
        if err:
            return err
        scoped_queryset(InitiativeProject.objects.all()).filter(
            initiative=initiative, project_id__in=self._ids(request)
        ).delete()
        return self._done(slug, initiative)


class InitiativeEpicsEndpoint(_LinkEndpoint):
    key = "epic_ids"

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug, initiative_id):
        initiative, err = self._initiative(slug, initiative_id, request.user)
        if err:
            return err
        ids = self._ids(request)
        valid = set(
            str(i)
            for i in epic_queryset(workspace_id=initiative.workspace_id).filter(pk__in=ids).values_list("id", flat=True)
        )
        if set(ids) - valid:
            return Response(
                {self.key: ["Some ids are not epics in this workspace."]}, status=status.HTTP_400_BAD_REQUEST
            )
        existing = set(str(link.epic_id) for link in initiative._epic_links)
        for i, eid in enumerate(ids):
            if eid not in existing:
                scoped_queryset(InitiativeEpic.objects.all()).create(
                    initiative=initiative, epic_id=eid, sort_order=(len(existing) + i + 1) * 10000
                )
        return self._done(slug, initiative)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def delete(self, request, slug, initiative_id):
        initiative, err = self._initiative(slug, initiative_id, request.user)
        if err:
            return err
        scoped_queryset(InitiativeEpic.objects.all()).filter(
            initiative=initiative, epic_id__in=self._ids(request)
        ).delete()
        return self._done(slug, initiative)


class InitiativeAnalyticsEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug, initiative_id):
        initiative = _queryset(slug).filter(pk=initiative_id).first()
        if initiative is None:
            return Response(NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        return Response(_rollup(initiative, request.user))


class WorkspaceEpicEndpoint(BaseAPIView):
    """Every epic in projects the viewer belongs to (for pickers)."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        visible = visible_project_ids(workspace.id, request.user)
        epics = epic_queryset(workspace_id=workspace.id).filter(project_id__in=visible).order_by("-created_at")
        project_id = request.GET.get("project_id")
        if project_id:
            epics = epics.filter(project_id=project_id)
        return Response(_serialize_epics(epics, request.user))
