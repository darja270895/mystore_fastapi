"""
Redis Pub/Sub subscriber logic for the shopping Card.

Publisher: CardService.publish_*  →  PUBLISH channel:card
Subscriber: lifespan listen_events → RedisPubSub.handle_message
Storage:    Redis HASH card:user:{user_id}  (field=product_id, value=amount)
"""

from __future__ import annotations

import json
import logging

from backend.card.card_events import CardEvent
from backend.card.card_ports import CardStore, EventCompletion

logger = logging.getLogger(__name__)


class RedisPubSub:
    """Applies CardEvent messages received on a subscribed channel."""

    def __init__(
        self,
        store: CardStore,
        completion: EventCompletion,
        channel: str,
    ):
        self.pub_sub_channel = channel
        self.store = store
        self.completion = completion

    async def handle_message(self, raw: str | bytes) -> None:
        if isinstance(raw, bytes):
            raw = raw.decode()
        try:
            event = CardEvent.model_validate(json.loads(raw))
        except Exception:
            logger.exception("Invalid card pub/sub payload: %s", raw)
            return

        # Multi-worker safe: only the first subscriber claims the event
        claimed = await self.completion.try_claim(event.event_id)
        if not claimed:
            logger.debug("Skip duplicate card event %s", event.event_id)
            return

        try:
            if event.action == "add":
                await self._apply_add(event)
            elif event.action == "remove":
                await self._apply_remove(event)
            elif event.action == "clear":
                await self._apply_clear(event)
            else:
                logger.warning("Unknown card action: %s", event.action)
                return

            # Signal publisher only after HASH write finished
            await self.completion.mark_applied(event.event_id)
        except Exception:
            logger.exception("Failed to apply card event %s", event.event_id)
            await self.completion.release_claim(event.event_id)

    async def _apply_add(self, event: CardEvent) -> None:
        if event.product_id is None:
            return
        new_amount = await self.store.apply_add(event)
        logger.info(
            "Card ADD user=%s product=%s amount=%s → total=%s (event=%s)",
            event.user_id,
            event.product_id,
            event.amount,
            new_amount,
            event.event_id,
        )

    async def _apply_remove(self, event: CardEvent) -> None:
        if event.product_id is None:
            return
        await self.store.apply_remove(event)
        logger.info(
            "Card REMOVE user=%s product=%s (event=%s)",
            event.user_id,
            event.product_id,
            event.event_id,
        )

    async def _apply_clear(self, event: CardEvent) -> None:
        await self.store.clear(event.user_id)
        logger.info("Card CLEAR user=%s (event=%s)", event.user_id, event.event_id)
