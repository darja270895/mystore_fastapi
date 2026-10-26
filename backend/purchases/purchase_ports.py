from __future__ import annotations

from typing import Protocol

from backend.purchases.purchase_events import PurchaseEvent
from backend.purchases.purchase_schemas import PurchaseCreate, PurchaseResponse


class PurchaseCoordinator(Protocol):
    """Application port for cross-process purchase coordination."""

    async def check_rate_limit(self, user_id: int) -> tuple[bool, int]: ...

    async def acquire_stock_lock(self, product_id: int, token: str) -> bool: ...

    async def release_stock_lock(self, product_id: int, token: str) -> None: ...


class PurchaseEvents(Protocol):
    """Application port for post-commit purchase side effects."""

    async def dispatch(self, event: PurchaseEvent) -> None: ...


class RecentPurchaseFeed(Protocol):
    async def list_recent(self, limit: int) -> list[dict]: ...


class PurchaseCreator(Protocol):
    """Use-case boundary consumed by Card checkout."""

    async def create_purchase(self, data: PurchaseCreate) -> PurchaseResponse: ...


class PurchaseEventSource(Protocol):
    async def read(self, last_id: str) -> list[tuple[str, PurchaseEvent]]: ...


class ConsumerLeadership(Protocol):
    async def acquire(self, token: str) -> bool: ...

    async def refresh(self, token: str) -> bool: ...

    async def release(self, token: str) -> None: ...
