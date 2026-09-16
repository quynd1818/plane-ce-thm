from .events import NotificationEvent
from .provider.base import NotificationProvider
from .provider.teams import TeamsProvider


class NotificationManager:
    def __init__(self, providers: list[NotificationProvider] | None = None):
        self.providers = providers or [TeamsProvider()]

    def publish(self, event: NotificationEvent) -> None:
        for provider in self.providers:
            provider.send(event)
