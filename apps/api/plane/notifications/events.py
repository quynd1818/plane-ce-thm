from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NotificationEvent:
    name: str
    payload: dict[str, Any]

    @property
    def setting_name(self) -> str:
        return {
            "issue.created": "TEAMS_NOTIFY_ISSUE_CREATED",
            "issue.assigned": "TEAMS_NOTIFY_ISSUE_ASSIGNED",
            "issue.updated": "TEAMS_NOTIFY_ISSUE_UPDATED",
            "issue.completed": "TEAMS_NOTIFY_ISSUE_COMPLETED",
            "issue.deleted": "TEAMS_NOTIFY_ISSUE_UPDATED",
            "comment.added": "TEAMS_NOTIFY_COMMENT",
            "cycle.started": "TEAMS_NOTIFY_CYCLE_STARTED",
            "cycle.completed": "TEAMS_NOTIFY_CYCLE_COMPLETED",
            "project.created": "TEAMS_NOTIFY_PROJECT_CREATED",
            "worklog.created": "TEAMS_NOTIFY_WORKLOG",
            "worklog.updated": "TEAMS_NOTIFY_WORKLOG",
            "worklog.deleted": "TEAMS_NOTIFY_WORKLOG",
            "custom_property.changed": "TEAMS_NOTIFY_CUSTOMIZATION",
            "template.changed": "TEAMS_NOTIFY_CUSTOMIZATION",
            "work_item_type.changed": "TEAMS_NOTIFY_CUSTOMIZATION",
            "recurring_issue.changed": "TEAMS_NOTIFY_AUTOMATION",
            "recurring_issue.generated": "TEAMS_NOTIFY_AUTOMATION",
            "intake_form.changed": "TEAMS_NOTIFY_INTAKE",
            "intake.submitted": "TEAMS_NOTIFY_INTAKE",
        }.get(self.name, "")
