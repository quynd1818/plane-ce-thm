from django.db import transaction

from .events import NotificationEvent


def publish_event(name: str, payload: dict) -> None:
    from plane.bgtasks.notification_task import dispatch_notification_event

    event_data = NotificationEvent(name=name, payload=payload).__dict__
    transaction.on_commit(lambda: dispatch_notification_event.delay(event_data))
