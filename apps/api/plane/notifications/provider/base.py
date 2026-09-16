from typing import Protocol

from plane.notifications.events import NotificationEvent


class NotificationProvider(Protocol):
    def send(self, event: NotificationEvent) -> None:
        ...
