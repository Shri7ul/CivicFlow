"""Notification delivery adapters.

Only in-app delivery is enabled. External adapters are interfaces, not
configured integrations, and never receive credentials in this repository.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class NotificationAdapterUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class DeliveryResult:
    delivered: bool
    error: str | None = None


class NotificationAdapter(ABC):
    """A delivery adapter receives a minimal payload, never a bearer token."""

    @abstractmethod
    def deliver(self, *, recipient_id: str, title: str, message: str) -> DeliveryResult:
        raise NotImplementedError


class InAppAdapter(NotificationAdapter):
    def deliver(self, *, recipient_id: str, title: str, message: str) -> DeliveryResult:
        del recipient_id, title, message
        return DeliveryResult(delivered=True)


class ExternalAdapter(NotificationAdapter):
    def deliver(self, *, recipient_id: str, title: str, message: str) -> DeliveryResult:
        del recipient_id, title, message
        raise NotificationAdapterUnavailable(
            "External notification delivery is not configured."
        )


ADAPTERS: dict[str, NotificationAdapter] = {
    "IN_APP": InAppAdapter(),
}


def get_notification_adapter(channel: str) -> NotificationAdapter:
    adapter = ADAPTERS.get(channel)
    if adapter is None:
        raise NotificationAdapterUnavailable(
            f"No notification adapter configured for {channel}."
        )
    return adapter
