from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from backend.card.card_events import CardEvent
from backend.card.card_schemas import CardResponse


class CardStore(Protocol):
    async def get(self, user_id: int) -> CardResponse: ...

    async def apply_add(self, event: CardEvent) -> int: ...

    async def apply_remove(self, event: CardEvent) -> None: ...

    async def clear(self, user_id: int) -> None: ...


class CardEventPublisher(Protocol):
    async def publish(self, event: CardEvent) -> str: ...


class EventCompletion(Protocol):
    async def try_claim(self, event_id: str) -> bool: ...

    async def mark_applied(self, event_id: str) -> None: ...

    async def wait_applied(self, event_id: str, timeout_s: float = 2.0) -> None: ...

    async def release_claim(self, event_id: str) -> None: ...


class CardEventStream(Protocol):
    def messages(self) -> AsyncIterator[str | None]: ...
