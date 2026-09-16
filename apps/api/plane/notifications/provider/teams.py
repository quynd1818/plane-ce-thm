import json
import logging
import os
from django.utils.html import strip_tags
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from plane.notifications.events import NotificationEvent

logger = logging.getLogger(__name__)


class NotificationDeliveryError(Exception):
    pass


class TeamsProvider:
    def __init__(self):
        self.enabled = os.environ.get("TEAMS_ENABLED", "false").lower() in {"1", "true", "yes"}
        self.webhook_url = os.environ.get("TEAMS_WEBHOOK_URL", "")

    def is_enabled_for(self, event: NotificationEvent) -> bool:
        return self.enabled and bool(self.webhook_url) and (
            not event.setting_name
            or os.environ.get(event.setting_name, "true").lower() in {"1", "true", "yes"}
        )

    def send(self, event: NotificationEvent) -> None:
        if not self.is_enabled_for(event):
            return
        request = Request(
            self.webhook_url,
            data=json.dumps(self._adaptive_card(event)).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                if response.status >= 300:
                    raise NotificationDeliveryError(f"Teams webhook returned HTTP {response.status}")
        except (HTTPError, URLError, TimeoutError) as exc:
            logger.exception("notification_failure", extra={"provider": "teams", "event": event.name})
            raise NotificationDeliveryError("Teams webhook delivery failed") from exc

    def _adaptive_card(self, event: NotificationEvent) -> dict:
        payload = event.payload
        facts = [
            {"title": "Project", "value": str(payload.get("project_name", ""))},
            {"title": "Issue", "value": str(payload.get("issue_name", ""))},
        ]
        for key, title in (
            ("assignee", "Assignee"),
            ("status", "Status"),
            ("priority", "Priority"),
            ("user", "User"),
            ("duration_seconds", "Duration (seconds)"),
            ("source", "Source"),
        ):
            if payload.get(key):
                facts.append({"title": title, "value": str(payload[key])})
        body = [
            {
                "type": "TextBlock",
                "text": payload.get("title", event.name),
                "weight": "Bolder",
                "size": "Medium",
                "wrap": True,
            },
            {"type": "FactSet", "facts": facts},
        ]
        description = strip_tags(str(payload.get("description", ""))).strip()
        if description:
            body.append({"type": "TextBlock", "text": description[:500], "wrap": True, "isSubtle": True})
        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": body,
        }
        link = payload.get("link")
        if link:
            card["actions"] = [{"type": "Action.OpenUrl", "title": "Open in Plane", "url": link}]
        return {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": card}]}
