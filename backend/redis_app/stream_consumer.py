"""
Simple Redis Stream consumer (one leader worker only).

Producer (purchase service)  →  XADD  →  stream:purchases
Consumer (this file)         →  XREAD →  save Notification
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from backend import models
from backend.database import AsyncSessionLocal
from backend.purchases.purchase_events import PurchaseEvent
from backend.purchases.purchase_ports import ConsumerLeadership, PurchaseEventSource

logger = logging.getLogger(__name__)


class PurchaseStreamConsumer:
    """Background worker: read new purchase messages and save notifications."""

    def __init__(
        self,
        source: PurchaseEventSource,
        leadership: ConsumerLeadership,
        leader_token: str,
    ):
        self._source = source
        self._leadership = leadership
        self._leader_token = leader_token
        self._task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> "PurchaseStreamConsumer":
        self._task = asyncio.create_task(
            self._listen(),
            name="purchase-stream-consumer",
        )
        logger.info("Purchase stream consumer started")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError, TimeoutError):
                await asyncio.wait_for(self._task, timeout=1.0)
            self._task = None
        logger.info("Purchase stream consumer stopped")

    async def _listen(self) -> None:
        last_id = "$"
        while True:
            if not await self._leadership.refresh(self._leader_token):
                logger.warning("Lost consumer leadership — stopping listener")
                break
            for message_id, event in await self._source.read(last_id):
                # One unprocessable message must not take the whole consumer down.
                try:
                    await self._save_notification(event)
                except Exception:
                    logger.exception("Failed to save notification for %s", message_id)
                last_id = message_id

    async def _save_notification(self, event: PurchaseEvent) -> None:
        async with AsyncSessionLocal() as session:
            session.add(
                models.Notification(
                    user_id=event.user_id,
                    kind="purchase_confirmed",
                    payload=event.model_dump_json(),
                    is_read=False,
                )
            )
            await session.commit()
        logger.info(
            "Notification saved for user=%s purchase=%s",
            event.user_id,
            event.purchase_id,
        )
