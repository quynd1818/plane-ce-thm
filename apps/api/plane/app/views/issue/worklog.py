import csv

from django.db import IntegrityError
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers.worklog import WorkLogCreateSerializer, WorkLogSerializer
from plane.app.views.base import BaseAPIView
from plane.db.models import Issue, ProjectMember, WorkLog


class IssueWorkLogEndpoint(BaseAPIView):
    def get_queryset(self, slug, project_id, issue_id):
        return WorkLog.objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            issue_id=issue_id,
            project__project_projectmember__member=self.request.user,
            project__project_projectmember__is_active=True,
        ).select_related("user")

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, issue_id):
        logs = self.get_queryset(slug, project_id, issue_id)
        return Response(WorkLogSerializer(logs, many=True).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id, issue_id):
        issue = Issue.objects.get(pk=issue_id, project_id=project_id, workspace__slug=slug)
        serializer = WorkLogCreateSerializer(
            data={**request.data, "issue": str(issue.id)},
            context={"issue": issue, "project_id": project_id},
        )
        serializer.is_valid(raise_exception=True)
        worklog = serializer.save(
            project=issue.project,
            workspace=issue.workspace,
            user=request.user,
        )
        return Response(WorkLogSerializer(worklog).data, status=status.HTTP_201_CREATED)


class IssueWorkLogDetailEndpoint(BaseAPIView):
    def get_worklog(self, slug, project_id, issue_id, worklog_id):
        return WorkLog.objects.get(
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
        if worklog.user_id != request.user.id and not ProjectMember.objects.filter(
            workspace__slug=slug, project_id=project_id, member=request.user, role=ROLE.ADMIN.value, is_active=True
        ).exists():
            return Response({"error": "Only the author or a project admin can edit this worklog."}, status=403)
        serializer = WorkLogSerializer(
            worklog,
            data=request.data,
            partial=True,
            context={"issue": worklog.issue},
        )
        serializer.is_valid(raise_exception=True)
        return Response(WorkLogSerializer(serializer.save()).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def delete(self, request, slug, project_id, issue_id, worklog_id):
        worklog = self.get_worklog(slug, project_id, issue_id, worklog_id)
        if worklog.user_id != request.user.id and not ProjectMember.objects.filter(
            workspace__slug=slug, project_id=project_id, member=request.user, role=ROLE.ADMIN.value, is_active=True
        ).exists():
            return Response({"error": "Only the author or a project admin can delete this worklog."}, status=403)
        worklog.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IssueTimerEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id, issue_id):
        issue = Issue.objects.get(pk=issue_id, project_id=project_id, workspace__slug=slug)
        if issue.project.is_time_tracking_enabled is not True:
            return Response({"error": "Time tracking is disabled for this project."}, status=400)
        active_timer = WorkLog.objects.filter(
            project_id=project_id, user=request.user, is_timer=True, ended_at__isnull=True
        ).first()
        if active_timer:
            return Response({"error": "You already have an active timer."}, status=400)
        try:
            worklog = WorkLog.objects.create(
                issue=issue,
                project=issue.project,
                workspace=issue.workspace,
                user=request.user,
                started_at=timezone.now(),
                duration_seconds=1,
                is_timer=True,
            )
        except IntegrityError:
            return Response({"error": "You already have an active timer."}, status=400)
        return Response(WorkLogSerializer(worklog).data, status=status.HTTP_201_CREATED)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def delete(self, request, slug, project_id, issue_id):
        worklog = WorkLog.objects.filter(
            project_id=project_id,
            issue_id=issue_id,
            user=request.user,
            is_timer=True,
            ended_at__isnull=True,
        ).first()
        if not worklog:
            return Response({"error": "No active timer found."}, status=404)
        worklog.ended_at = timezone.now()
        worklog.duration_seconds = max(1, int((worklog.ended_at - worklog.started_at).total_seconds()))
        worklog.save(update_fields=["ended_at", "duration_seconds", "updated_at"])
        return Response(WorkLogSerializer(worklog).data)


class ProjectWorkLogSummaryEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        queryset = WorkLog.objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            project__project_projectmember__member=request.user,
            project__project_projectmember__is_active=True,
            project__is_time_tracking_enabled=True,
        )
        issue_id = request.GET.get("issue_id")
        user_id = request.GET.get("user_id")
        started_after = request.GET.get("started_after")
        started_before = request.GET.get("started_before")
        if issue_id:
            queryset = queryset.filter(issue_id=issue_id)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if started_after:
            queryset = queryset.filter(started_at__date__gte=started_after)
        if started_before:
            queryset = queryset.filter(started_at__date__lte=started_before)
        total = queryset.aggregate(total=Sum("duration_seconds"))["total"] or 0
        group_by = request.GET.get("group_by")
        grouped = []
        if group_by == "issue":
            grouped = list(
                queryset.values("issue_id")
                .annotate(total_seconds=Sum("duration_seconds"))
                .order_by("-total_seconds")
            )
        elif group_by == "user":
            grouped = list(
                queryset.values("user_id")
                .annotate(total_seconds=Sum("duration_seconds"))
                .order_by("-total_seconds")
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


class ProjectWorkLogReportEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        queryset = WorkLog.objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            project__is_time_tracking_enabled=True,
            project__project_projectmember__member=request.user,
            project__project_projectmember__is_active=True,
        ).select_related("issue", "user")
        issue_id = request.GET.get("issue_id")
        user_id = request.GET.get("user_id")
        started_after = request.GET.get("started_after")
        started_before = request.GET.get("started_before")
        if issue_id:
            queryset = queryset.filter(issue_id=issue_id)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if started_after:
            queryset = queryset.filter(started_at__date__gte=started_after)
        if started_before:
            queryset = queryset.filter(started_at__date__lte=started_before)

        if request.GET.get("format") == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="plane-worklogs.csv"'
            writer = csv.writer(response)
            writer.writerow(["work_item", "user", "description", "duration_seconds", "started_at", "ended_at"])
            for worklog in queryset:
                writer.writerow(
                    [
                        worklog.issue.name,
                        worklog.user.email,
                        worklog.description,
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
