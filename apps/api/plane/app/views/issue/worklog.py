import csv

from django.db import IntegrityError
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.negotiation import DefaultContentNegotiation

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers.worklog import WorkLogCreateSerializer, WorkLogSerializer
from plane.app.views.base import BaseAPIView
from plane.db.models import Issue, Project, WorkLog
from plane.notifications.service import publish_event
from plane.utils.worklog_approval import can_modify_worklog, initial_status, is_worklog_approver


from plane.utils.project_rbac_scope import scoped_queryset


class IssueWorkLogEndpoint(BaseAPIView):
    rbac_policy = {"GET": "worklogs.read"}

    def get_queryset(self, slug, project_id, issue_id):
        return (
            scoped_queryset(WorkLog.objects.all())
            .filter(
                workspace__slug=slug,
                project_id=project_id,
                issue_id=issue_id,
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
            )
            .select_related("user")
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, issue_id):
        logs = self.get_queryset(slug, project_id, issue_id)
        return Response(WorkLogSerializer(logs, many=True).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id, issue_id):
        issue = scoped_queryset(Issue.objects.all()).get(pk=issue_id, project_id=project_id, workspace__slug=slug)
        serializer = WorkLogCreateSerializer(
            data={**request.data, "issue": str(issue.id)},
            context={"issue": issue, "project_id": project_id},
        )
        serializer.is_valid(raise_exception=True)
        worklog = serializer.save(
            project=issue.project,
            workspace=issue.workspace,
            user=request.user,
            status=initial_status(issue.project),
        )
        return Response(WorkLogSerializer(worklog).data, status=status.HTTP_201_CREATED)


class IssueWorkLogDetailEndpoint(BaseAPIView):
    def get_worklog(self, slug, project_id, issue_id, worklog_id):
        return scoped_queryset(WorkLog.objects.all()).get(
            pk=worklog_id,
            workspace__slug=slug,
            project_id=project_id,
            issue_id=issue_id,
            project__project_projectmember__member=self.request.user,
            project__project_projectmember__is_active=True,
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def patch(self, request, slug, project_id, issue_id, worklog_id):
        worklog = self.get_worklog(slug, project_id, issue_id, worklog_id)
        allowed, reason = can_modify_worklog(worklog, request.user)
        if not allowed:
            return Response({"error": reason}, status=403)
        serializer = WorkLogSerializer(
            worklog,
            data=request.data,
            partial=True,
            context={"issue": worklog.issue},
        )
        serializer.is_valid(raise_exception=True)
        # an author editing a rejected log re-submits it
        extra = {}
        if worklog.user_id == request.user.id and worklog.status == WorkLog.STATUS_REJECTED:
            extra = {
                "status": initial_status(worklog.project),
                "review_note": "",
                "reviewed_by": None,
                "reviewed_at": None,
            }
        return Response(WorkLogSerializer(serializer.save(**extra)).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def delete(self, request, slug, project_id, issue_id, worklog_id):
        worklog = self.get_worklog(slug, project_id, issue_id, worklog_id)
        allowed, reason = can_modify_worklog(worklog, request.user)
        if not allowed:
            return Response({"error": reason}, status=403)
        worklog.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IssueTimerEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id, issue_id):
        issue = scoped_queryset(Issue.objects.all()).get(pk=issue_id, project_id=project_id, workspace__slug=slug)
        if issue.project.is_time_tracking_enabled is not True:
            return Response({"error": "Time tracking is disabled for this project."}, status=400)
        active_timer = (
            scoped_queryset(WorkLog.objects.all())
            .filter(project_id=project_id, user=request.user, is_timer=True, ended_at__isnull=True)
            .first()
        )
        if active_timer:
            return Response({"error": "You already have an active timer."}, status=400)
        try:
            worklog = scoped_queryset(WorkLog.objects.all()).create(
                issue=issue,
                project=issue.project,
                workspace=issue.workspace,
                user=request.user,
                started_at=timezone.now(),
                duration_seconds=1,
                is_timer=True,
                status=initial_status(issue.project),
            )
        except IntegrityError:
            return Response({"error": "You already have an active timer."}, status=400)
        return Response(WorkLogSerializer(worklog).data, status=status.HTTP_201_CREATED)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def delete(self, request, slug, project_id, issue_id):
        worklog = (
            scoped_queryset(WorkLog.objects.all())
            .filter(
                workspace__slug=slug,
                project_id=project_id,
                issue_id=issue_id,
                user=request.user,
                is_timer=True,
                ended_at__isnull=True,
            )
            .first()
        )
        if not worklog:
            return Response({"error": "No active timer found."}, status=404)
        worklog.ended_at = timezone.now()
        worklog.duration_seconds = max(1, int((worklog.ended_at - worklog.started_at).total_seconds()))
        worklog.save(update_fields=["ended_at", "duration_seconds", "updated_at"])
        return Response(WorkLogSerializer(worklog).data)


def _apply_worklog_filters(queryset, params, project_id=None):
    """Apply optional issue/user/date/status filters. Raises ValidationError on bad dates (-> HTTP 400).

    status: "submitted" | "approved" | "rejected" | "all". When omitted and the
    project requires approval, only approved logs are counted so reports never
    include hours that were not signed off.
    """
    issue_id = params.get("issue_id")
    user_id = params.get("user_id")
    started_after = params.get("started_after")
    started_before = params.get("started_before")
    if issue_id:
        queryset = queryset.filter(issue_id=issue_id)
    if user_id:
        queryset = queryset.filter(user_id=user_id)
    status_filter = params.get("status")
    if status_filter and status_filter != "all":
        if status_filter not in dict(WorkLog.STATUS_CHOICES):
            raise ValidationError({"status": "Expected submitted, approved, rejected or all."})
        queryset = queryset.filter(status=status_filter)
    elif not status_filter and project_id is not None:
        if Project.objects.filter(pk=project_id, is_worklog_approval_enabled=True).exists():
            queryset = queryset.filter(status=WorkLog.STATUS_APPROVED)
    for key, value in (("started_after", started_after), ("started_before", started_before)):
        if not value:
            continue
        parsed = parse_date(value)
        if parsed is None:
            raise ValidationError({key: "Expected a date in YYYY-MM-DD format."})
        if key == "started_after":
            queryset = queryset.filter(started_at__date__gte=parsed)
        else:
            queryset = queryset.filter(started_at__date__lte=parsed)
    return queryset


class ProjectWorkLogSummaryEndpoint(BaseAPIView):
    rbac_policy = {"GET": "worklogs.read"}

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        queryset = scoped_queryset(WorkLog.objects.all()).filter(
            workspace__slug=slug,
            project_id=project_id,
            project__project_projectmember__member=request.user,
            project__project_projectmember__is_active=True,
            project__is_time_tracking_enabled=True,
        )
        queryset = _apply_worklog_filters(queryset, request.GET, project_id=project_id)
        total = queryset.aggregate(total=Sum("duration_seconds"))["total"] or 0
        group_by = request.GET.get("group_by")
        grouped = []
        if group_by == "issue":
            grouped = list(
                queryset.values("issue_id").annotate(total_seconds=Sum("duration_seconds")).order_by("-total_seconds")
            )
        elif group_by == "user":
            grouped = list(
                queryset.values("user_id").annotate(total_seconds=Sum("duration_seconds")).order_by("-total_seconds")
            )
        elif group_by == "day":
            grouped = list(
                queryset.annotate(day=TruncDate("started_at"))
                .values("day")
                .annotate(total_seconds=Sum("duration_seconds"))
                .order_by("-day")
            )
        return Response(
            {
                "total_seconds": total,
                "total_hours": round(total / 3600, 2),
                "group_by": group_by,
                "groups": grouped,
            }
        )


def _csv_text(value):
    # Spreadsheet programs may execute formulas in otherwise correctly quoted CSV.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


class WorklogReportNegotiation(DefaultContentNegotiation):
    def filter_renderers(self, renderers, format):
        return renderers if format == "csv" else super().filter_renderers(renderers, format)


class ProjectWorkLogReportEndpoint(BaseAPIView):
    content_negotiation_class = WorklogReportNegotiation
    rbac_export = True

    rbac_policy = {"GET": "worklogs.read"}

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        queryset = (
            scoped_queryset(WorkLog.objects.all())
            .filter(
                workspace__slug=slug,
                project_id=project_id,
                project__is_time_tracking_enabled=True,
                project__project_projectmember__member=request.user,
                project__project_projectmember__is_active=True,
            )
            .select_related("issue", "user")
        )
        queryset = _apply_worklog_filters(queryset, request.GET, project_id=project_id)

        if request.GET.get("format") == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="plane-worklogs.csv"'
            writer = csv.writer(response)
            writer.writerow(["work_item", "user", "description", "duration_seconds", "started_at", "ended_at"])
            for worklog in queryset:
                writer.writerow(
                    [
                        _csv_text(worklog.issue.name),
                        _csv_text(worklog.user.email),
                        _csv_text(worklog.description),
                        worklog.duration_seconds,
                        worklog.started_at.isoformat(),
                        worklog.ended_at.isoformat() if worklog.ended_at else "",
                    ]
                )
            return response

        return Response(
            {
                "results": [
                    {
                        **WorkLogSerializer(worklog).data,
                        "issue_name": worklog.issue.name,
                        "user_email": worklog.user.email,
                    }
                    for worklog in queryset
                ],
                "total_seconds": queryset.aggregate(total=Sum("duration_seconds"))["total"] or 0,
            }
        )


class ProjectWorkLogPendingEndpoint(BaseAPIView):
    """Worklogs waiting for review — approvers only."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        if not is_worklog_approver(project, request.user):
            return Response({"error": "Only worklog approvers can view the review queue."}, status=403)
        queryset = (
            scoped_queryset(WorkLog.objects.all())
            .filter(project=project, status=WorkLog.STATUS_SUBMITTED)
            .exclude(is_timer=True, ended_at__isnull=True)
            .select_related("issue", "user")
            .order_by("started_at")
        )
        return Response(
            {
                "results": [
                    {**WorkLogSerializer(w).data, "issue_name": w.issue.name, "issue_sequence_id": w.issue.sequence_id}
                    for w in queryset
                ],
                "count": queryset.count(),
                "total_seconds": queryset.aggregate(total=Sum("duration_seconds"))["total"] or 0,
            }
        )


class WorkLogReviewEndpoint(BaseAPIView):
    """POST {action: approve|reject|reopen, note?} — approvers only."""

    ACTIONS = {
        "approve": WorkLog.STATUS_APPROVED,
        "reject": WorkLog.STATUS_REJECTED,
        "reopen": WorkLog.STATUS_SUBMITTED,
    }

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def post(self, request, slug, project_id, issue_id, worklog_id):
        worklog = (
            scoped_queryset(WorkLog.objects.all())
            .select_related("project", "issue", "user")
            .get(pk=worklog_id, workspace__slug=slug, project_id=project_id, issue_id=issue_id)
        )
        if not is_worklog_approver(worklog.project, request.user):
            return Response({"error": "Only worklog approvers can review worklogs."}, status=403)
        action = request.data.get("action")
        if action not in self.ACTIONS:
            return Response({"error": "action must be one of approve, reject, reopen."}, status=400)
        if worklog.is_timer and worklog.ended_at is None:
            return Response({"error": "Stop the timer before reviewing this worklog."}, status=400)
        note = str(request.data.get("note") or "").strip()
        if action == "reject" and not note:
            return Response({"note": "A note is required when rejecting."}, status=400)

        worklog.status = self.ACTIONS[action]
        worklog.review_note = note
        worklog.reviewed_by = None if action == "reopen" else request.user
        worklog.reviewed_at = None if action == "reopen" else timezone.now()
        worklog.save(update_fields=["status", "review_note", "reviewed_by", "reviewed_at", "updated_at"])

        publish_event(
            "worklog.reviewed",
            {
                "title": {"approve": "Worklog Approved", "reject": "Worklog Rejected", "reopen": "Worklog Reopened"}[
                    action
                ],
                "project_name": worklog.project.name,
                "issue_name": worklog.issue.name,
                "user": worklog.user.display_name or worklog.user.email,
                "duration_seconds": worklog.duration_seconds,
                "description": note,
            },
        )
        return Response(WorkLogSerializer(worklog).data)
