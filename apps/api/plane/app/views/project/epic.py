# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""THM epics (project level).

* ``GET/POST /projects/<id>/epics/``                       list with rollup / create
* ``GET     /projects/<id>/epics/<epic_id>/``              detail + children
* ``DELETE  /projects/<id>/epics/<epic_id>/``              demote to a normal work item
* ``POST/DELETE /projects/<id>/epics/<epic_id>/work-items/`` attach / detach children
* ``POST    /projects/<id>/epics/convert/``                promote a work item to an epic
"""

import json
from collections import defaultdict

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import IssueCreateSerializer
from plane.app.views.base import BaseAPIView
from plane.bgtasks.issue_activities_task import issue_activity
from plane.db.models import Issue, IssueAssignee, IssueLabel, Project
from plane.utils.epic import ensure_project_epic_type, epic_queryset, rollup_for_epics, visible_issues
from plane.utils.host import base_host

from plane.utils.project_rbac_scope import scoped_queryset


EPIC_FIELDS = (
    "id",
    "name",
    "sequence_id",
    "state_id",
    "priority",
    "start_date",
    "target_date",
    "project_id",
    "completed_at",
    "created_at",
    "updated_at",
    "created_by_id",
)


def _serialize_epics(epics, user):
    rows = list(visible_issues(epics, user).values(*EPIC_FIELDS))
    ids = [r["id"] for r in rows]
    assignees, labels = defaultdict(list), defaultdict(list)
    for ia in scoped_queryset(IssueAssignee.objects.all()).filter(issue_id__in=ids).values("issue_id", "assignee_id"):
        assignees[ia["issue_id"]].append(str(ia["assignee_id"]))
    for il in scoped_queryset(IssueLabel.objects.all()).filter(issue_id__in=ids).values("issue_id", "label_id"):
        labels[il["issue_id"]].append(str(il["label_id"]))
    rollup = rollup_for_epics(ids, user)
    for r in rows:
        r["assignee_ids"] = assignees[r["id"]]
        r["label_ids"] = labels[r["id"]]
        r["rollup"] = rollup[str(r["id"])]
    return rows


def _project_epics(slug, project_id, user):
    return epic_queryset(project_id=project_id).filter(
        workspace__slug=slug,
        project__project_projectmember__member=user,
        project__project_projectmember__is_active=True,
    )


class ProjectEpicEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        epics = _project_epics(slug, project_id, request.user).order_by("-created_at")
        state_group = request.GET.get("state_group")
        if state_group:
            epics = epics.filter(state__group=state_group)
        return Response(_serialize_epics(epics, request.user))

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        if not project.is_epic_enabled:
            return Response({"error": "Epics are not enabled for this project."}, status=status.HTTP_400_BAD_REQUEST)
        epic_type = ensure_project_epic_type(project, request.user)
        payload = {k: v for k, v in request.data.items() if k != "parent_id"}  # epics have no parent
        serializer = IssueCreateSerializer(
            data=payload,
            context={
                "project_id": project_id,
                "workspace_id": project.workspace_id,
                "default_assignee_id": project.default_assignee_id,
            },
        )
        serializer.is_valid(raise_exception=True)
        issue = serializer.save(type=epic_type)
        issue_activity.delay(
            type="issue.activity.created",
            requested_data=json.dumps(payload, cls=DjangoJSONEncoder),
            actor_id=str(request.user.id),
            issue_id=str(issue.id),
            project_id=str(project_id),
            current_instance=None,
            epoch=int(timezone.now().timestamp()),
            notification=True,
            origin=base_host(request=request, is_app=True),
        )
        return Response(
            _serialize_epics(scoped_queryset(Issue.issue_objects.all()).filter(pk=issue.pk), request.user)[0],
            status=status.HTTP_201_CREATED,
        )


class ProjectEpicDetailEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, epic_id):
        epics = _project_epics(slug, project_id, request.user).filter(pk=epic_id)
        rows = _serialize_epics(epics, request.user)
        if not rows:
            return Response({"error": "Epic not found."}, status=status.HTTP_404_NOT_FOUND)
        data = rows[0]
        children = list(
            visible_issues(scoped_queryset(Issue.issue_objects.all()).filter(parent_id=epic_id), request.user)
            .order_by("sequence_id")
            .values("id", "name", "sequence_id", "state_id", "priority", "target_date", "project_id", "completed_at")
        )
        child_ids = [c["id"] for c in children]
        assignees = defaultdict(list)
        for ia in (
            scoped_queryset(IssueAssignee.objects.all())
            .filter(issue_id__in=child_ids)
            .values("issue_id", "assignee_id")
        ):
            assignees[ia["issue_id"]].append(str(ia["assignee_id"]))
        for c in children:
            c["assignee_ids"] = assignees[c["id"]]
        data["work_items"] = children
        return Response(data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def delete(self, request, slug, project_id, epic_id):
        """Demote: the work item stays, its children are detached."""
        epic = _project_epics(slug, project_id, request.user).filter(pk=epic_id).first()
        if epic is None:
            return Response({"error": "Epic not found."}, status=status.HTTP_404_NOT_FOUND)
        scoped_queryset(Issue.issue_objects.all()).filter(parent_id=epic_id).update(parent=None)
        epic.type = None
        epic.save(update_fields=["type", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectEpicWorkItemsEndpoint(BaseAPIView):
    """Attach / detach children: ``{"issue_ids": [...]}``."""

    def _epic(self, slug, project_id, epic_id, user):
        return _project_epics(slug, project_id, user).filter(pk=epic_id).first()

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id, epic_id):
        epic = self._epic(slug, project_id, epic_id, request.user)
        if epic is None:
            return Response({"error": "Epic not found."}, status=status.HTTP_404_NOT_FOUND)
        ids = [str(i) for i in request.data.get("issue_ids") or []]
        if not ids:
            return Response({"issue_ids": ["Required."]}, status=status.HTTP_400_BAD_REQUEST)
        candidates = (
            scoped_queryset(Issue.issue_objects.all()).filter(pk__in=ids, project_id=project_id).exclude(pk=epic_id)
        )
        # an epic cannot be nested under another epic; a work item with children keeps them
        candidates = candidates.exclude(type__is_epic=True)
        found = set(str(i) for i in candidates.values_list("id", flat=True))
        missing = [i for i in ids if i not in found]
        if missing:
            return Response(
                {"issue_ids": [f"Not attachable (other project, epic, or missing): {', '.join(missing)}"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        candidates.update(parent=epic, updated_at=timezone.now())
        return Response(
            _serialize_epics(scoped_queryset(Issue.issue_objects.all()).filter(pk=epic.pk), request.user)[0]
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def delete(self, request, slug, project_id, epic_id):
        epic = self._epic(slug, project_id, epic_id, request.user)
        if epic is None:
            return Response({"error": "Epic not found."}, status=status.HTTP_404_NOT_FOUND)
        ids = [str(i) for i in request.data.get("issue_ids") or []]
        scoped_queryset(Issue.issue_objects.all()).filter(pk__in=ids, parent_id=epic_id).update(
            parent=None, updated_at=timezone.now()
        )
        return Response(
            _serialize_epics(scoped_queryset(Issue.issue_objects.all()).filter(pk=epic.pk), request.user)[0]
        )


class ProjectEpicConvertEndpoint(BaseAPIView):
    """Promote an existing work item to an epic: ``{"issue_id": ...}``."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        if not project.is_epic_enabled:
            return Response({"error": "Epics are not enabled for this project."}, status=status.HTTP_400_BAD_REQUEST)
        issue = (
            scoped_queryset(Issue.issue_objects.all())
            .filter(pk=request.data.get("issue_id"), project_id=project_id)
            .first()
        )
        if issue is None:
            return Response({"error": "Work item not found."}, status=status.HTTP_404_NOT_FOUND)
        if issue.parent_id:
            return Response(
                {"error": "A work item that is itself a child cannot become an epic. Detach it first."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        issue.type = ensure_project_epic_type(project, request.user)
        issue.save(update_fields=["type", "updated_at"])
        return Response(
            _serialize_epics(scoped_queryset(Issue.issue_objects.all()).filter(pk=issue.pk), request.user)[0]
        )
