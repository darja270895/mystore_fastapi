"""
Purchase business logic — Redis + AsyncIO showcase.

AsyncIO: TaskGroup for concurrent user+product load; try/finally for lock release.
Redis: rate limit, lock, cache; stream producer (XADD); pub/sub + zset extras.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from backend.redis_app.adapters.purchase import RedisPurchaseCoordinator, RedisPurchaseEvents, RedisRecentPurchaseFeed
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.purchases.purchase_db_interface import PurchaseDbInterface
from backend.purchases.purchase_events import PurchaseEvent
from backend.purchases.purchase_ports import (
    PurchaseCoordinator as PurchaseCoordinatorPort,
    PurchaseEvents as PurchaseEventsPort,
    RecentPurchaseFeed as RecentPurchaseFeedPort,
)
from backend.purchases.purchase_schemas import PurchaseCreate, PurchaseResponse
from backend.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class PurchaseService:
    def __init__(
            self,
            db_session: AsyncSession,
            coordinator: PurchaseCoordinatorPort | None = None,  # port ← adapter
            events: PurchaseEventsPort | None = None,  # port ← adapter
            recent_feed: RecentPurchaseFeedPort | None = None,  # port ← adapter
    ):
        self.db_session = db_session
        self.coordinator = coordinator
        self.events = events
        self.recent_feed = recent_feed
        self.db = PurchaseDbInterface(db_session)

    async def create_purchase(self, data: PurchaseCreate) -> PurchaseResponse:

        await self._enforce_rate_limit(data.user_id)
        # Concurrent I/O
        user, product = await self._load_user_and_product(data.user_id, data.product_id)

        lock_token = uuid4().hex
        lock_held = await self._acquire_stock_lock(data.product_id, lock_token)
        try:
            # Re-read product inside the lock (avoid race on stock)
            product = await self.db.get_product(data.product_id)
            if product is None:
                raise HTTPException(status_code=404, detail="Product not found")
            if product.stock < data.amount:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock: have {product.stock}, need {data.amount}",
                )

            purchase = await self.db.create_purchase(data)
            await self.db.decrement_stock(product, data.amount)
            await self.db.create_stock_movement(
                product_id=product.id,
                delta=-data.amount,
                reason="purchase",
                purchase_id=purchase.id,
            )
            await self.db_session.commit()
            await self.db_session.refresh(purchase)

            event = PurchaseEvent(
                purchase_id=purchase.id,
                user_id=user.id,
                product_id=product.id,
                amount=data.amount,
                product_name=product.name,
                total_price=float(product.price) * data.amount,
            )
            await self._emit_async_side_effects(event)

            return PurchaseResponse.model_validate(purchase)
        finally:
            if lock_held:
                await self._release_stock_lock(data.product_id, lock_token)

    async def list_purchases(self) -> list[PurchaseResponse]:
        rows = await self.db.get_all()
        return [PurchaseResponse.model_validate(row) for row in rows]

    async def list_stock_movements(self, product_id: int | None = None):
        return await self.db.list_stock_movements(product_id=product_id)

    async def list_notifications(self, user_id: int):
        return await self.db.list_notifications(user_id=user_id)

    async def recent_purchases(self) -> list[dict]:
        """Read the recent-purchase feed without a SQL query."""
        if not self.recent_feed:
            return []
        return await self.recent_feed.list_recent(limit=100)

    async def _load_user_and_product(self, user_id: int, product_id: int):
        """

        TaskGroup runs both awaits concurrently on the same event loop.
        We open 2 short-lived async sessions for true concurrency, as async SQLite connection is not concurrently-safe.

        """

        async def fetch_user():
            async with AsyncSessionLocal() as session:
                return await PurchaseDbInterface(session).get_user(user_id)

        async def fetch_product():
            async with AsyncSessionLocal() as session:
                return await PurchaseDbInterface(session).get_product(product_id)

        async with asyncio.TaskGroup() as tg:
            user_task = tg.create_task(fetch_user())
            product_task = tg.create_task(fetch_product())

        user = user_task.result()
        product = product_task.result()

        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        return user, product

    async def _enforce_rate_limit(self, user_id: int) -> None:
        if not self.coordinator:
            return
        allowed, count = await self.coordinator.check_rate_limit(user_id)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded (request #{count} in the current window)",
            )

    async def _acquire_stock_lock(self, product_id: int, token: str) -> bool:
        if not self.coordinator:
            return False
        acquired = await self.coordinator.acquire_stock_lock(product_id, token)
        if not acquired:
            raise HTTPException(
                status_code=409,
                detail="Product stock is locked by another purchase — retry shortly",
            )
        return True

    async def _release_stock_lock(self, product_id: int, token: str) -> None:
        if not self.coordinator:
            return
        await self.coordinator.release_stock_lock(product_id, token)

    async def _emit_async_side_effects(self, event: PurchaseEvent) -> None:
        """Dispatch post-commit side effects through the application port."""
        if not self.events:
            logger.info("Purchase event adapter unavailable — skipping side effects")
            return
        await self.events.dispatch(event)
