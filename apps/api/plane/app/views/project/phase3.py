from django.utils.html import escape
from django.utils import timezone
from django.db.models import Count, Sum
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import IntakeFormSerializer, RecurringIssueSerializer
from plane.app.views.base import BaseAPIView
from plane.db.models import Intake, IntakeForm, Issue, Project, RecurringIssue, WorkLog


class ProjectPhase3Mixin(BaseAPIView):
    def project_queryset(self, model, slug, project_id):
        return model.objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            project__project_projectmember__member=self.request.user,
            project__project_projectmember__is_active=True,
        )


class IntakeFormEndpoint(ProjectPhase3Mixin):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def get(self, request, slug, project_id):
        forms = self.project_queryset(IntakeForm, slug, project_id)
        return Response(IntakeFormSerializer(forms, many=True).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id):
        intake = Intake.objects.filter(project_id=project_id, workspace__slug=slug).first()
        if not intake:
            return Response({"detail": "Intake not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = IntakeFormSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        form = serializer.save(project_id=project_id, intake=intake)
        return Response(IntakeFormSerializer(form).data, status=status.HTTP_201_CREATED)


class IntakeFormDetailEndpoint(ProjectPhase3Mixin):
    def get_form(self, slug, project_id, form_id):
        return self.project_queryset(IntakeForm, slug, project_id).get(pk=form_id)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def patch(self, request, slug, project_id, form_id):
        form = self.get_form(slug, project_id, form_id)
        serializer = IntakeFormSerializer(form, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(IntakeFormSerializer(serializer.save()).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def delete(self, request, slug, project_id, form_id):
        self.get_form(slug, project_id, form_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicIntakeFormEndpoint(BaseAPIView):
    authentication_classes = []
    permission_classes = []

    def get_form(self, public_key):
        return IntakeForm.objects.filter(public_key=public_key, is_active=True, deleted_at__isnull=True).select_related(
            "project", "intake"
        ).first()

    def get(self, request, public_key):
        form = self.get_form(public_key)
        if not form:
            return Response({"detail": "Form not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(IntakeFormSerializer(form).data)

    def post(self, request, public_key):
        form = self.get_form(public_key)
        if not form:
            return Response({"detail": "Form not found."}, status=status.HTTP_404_NOT_FOUND)
        values = request.data if isinstance(request.data, dict) else {}
        field_keys = {field["key"] for field in form.fields}
        unknown = set(values) - field_keys
        if unknown:
            return Response({"detail": f"Unknown fields: {sorted(unknown)}"}, status=status.HTTP_400_BAD_REQUEST)
        missing = [
            field["key"]
            for field in form.fields
            if field.get("required") and values.get(field["key"]) in (None, "", [])
        ]
        if missing:
            return Response({"detail": f"Missing required fields: {missing}"}, status=status.HTTP_400_BAD_REQUEST)
        for field in form.fields:
            value = values.get(field["key"])
            if value in (None, ""):
                continue
            if field.get("type") == "select" and value not in field.get("options", []):
                return Response(
                    {"detail": f"Invalid option for field: {field['key']}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        title = str(values.get("title") or values.get("name") or form.name)[:255]
        description = escape(str(values.get("description") or ""))
        submission_properties = {
            key: value for key, value in values.items() if key not in {"title", "name", "description"}
        }
        issue = Issue.objects.create(
            project=form.project,
            workspace=form.workspace,
            name=title,
            description_html=f"<p>{description}</p>",
            state=form.project.default_state,
            priority="none",
            custom_properties={**form.default_values, **submission_properties},
        )
        form.intake.issue_intake.create(
            project=form.project,
            workspace=form.workspace,
            issue=issue,
            extra=values,
            source="PUBLIC_FORM",
        )
        return Response({"id": str(issue.id), "message": "Submission received."}, status=status.HTTP_201_CREATED)


class RecurringIssueEndpoint(ProjectPhase3Mixin):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def get(self, request, slug, project_id):
        return Response(RecurringIssueSerializer(self.project_queryset(RecurringIssue, slug, project_id), many=True).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        serializer = RecurringIssueSerializer(
            data=request.data,
            context={"project_id": project_id, "workspace_id": project.workspace_id},
        )
        serializer.is_valid(raise_exception=True)
        value = serializer.save(project_id=project_id)
        return Response(RecurringIssueSerializer(value).data, status=status.HTTP_201_CREATED)


class RecurringIssueDetailEndpoint(ProjectPhase3Mixin):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def patch(self, request, slug, project_id, recurring_id):
        value = self.project_queryset(RecurringIssue, slug, project_id).get(pk=recurring_id)
        serializer = RecurringIssueSerializer(
            value,
            data=request.data,
            partial=True,
            context={"project_id": project_id, "workspace_id": value.project.workspace_id},
        )
        serializer.is_valid(raise_exception=True)
        return Response(RecurringIssueSerializer(serializer.save()).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def delete(self, request, slug, project_id, recurring_id):
        self.project_queryset(RecurringIssue, slug, project_id).get(pk=recurring_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectDashboardSummaryEndpoint(ProjectPhase3Mixin):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def get(self, request, slug, project_id):
        issues = Issue.issue_objects.filter(workspace__slug=slug, project_id=project_id)
        worklogs = WorkLog.objects.filter(workspace__slug=slug, project_id=project_id)
        return Response(
            {
                "work_items": {
                    "total": issues.count(),
                    "completed": issues.filter(state__group="completed").count(),
                    "overdue": issues.filter(target_date__lt=timezone.now().date()).exclude(
                        state__group__in=["completed", "cancelled"]
                    ).count(),
                    "unassigned": issues.filter(issue_assignee__isnull=True).count(),
                },
                "worklogs": {
                    "total_seconds": worklogs.aggregate(total=Sum("duration_seconds"))["total"] or 0,
                    "entries": worklogs.count(),
                },
                "workload": list(
                    worklogs.values("user_id", "user__display_name", "user__email")
                    .annotate(total_seconds=Sum("duration_seconds"), entries=Count("id"))
                    .order_by("-total_seconds")[:20]
                ),
            }
        )
