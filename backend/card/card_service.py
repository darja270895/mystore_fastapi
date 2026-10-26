"""
Card business logic — Redis Pub/Sub showcase.

Publisher (this service)  →  PUBLISH channel:card
Subscriber (redis_lifespan) → writes Redis HASH card:user:{id}
Checkout                  →  delegates to PurchaseService (separate module)
"""

from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.card.card_schemas import (
    CardAdd,
    CardPublishResponse,
    CardRemove,
    CardResponse,
)
from backend.card.card_events import CardEvent
from backend.card.card_ports import CardEventPublisher, CardStore, EventCompletion
from backend.purchases.purchase_db_interface import PurchaseDbInterface
from backend.purchases.purchase_ports import PurchaseCreator
from backend.purchases.purchase_schemas import PurchaseCreate, PurchaseResponse

logger = logging.getLogger(__name__)


class CardService:
    def __init__(
        self,
        db_session: AsyncSession,
        store: CardStore | None = None,
        publisher: CardEventPublisher | None = None,
        completion: EventCompletion | None = None,
        purchase_creator: PurchaseCreator | None = None,
    ):
        self.db_session = db_session
        self.store = store
        self.publisher = publisher
        self.completion = completion
        self.purchase_creator = purchase_creator
        self.db = PurchaseDbInterface(db_session)

    async def add_item(self, data: CardAdd) -> CardPublishResponse:
        self._require_redis()
        user = await self.db.get_user(data.user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        product = await self.db.get_product(data.product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")

        event = CardEvent(
            action="add",
            user_id=data.user_id,
            product_id=data.product_id,
            amount=data.amount,
            product_name=product.name,
        )
        channel = await self._publish(event)
        await self._wait_applied(event.event_id)
        card = await self.get_card(data.user_id)
        return CardPublishResponse(
            event_id=event.event_id,
            channel=channel,
            card=card,
        )

    async def remove_item(self, data: CardRemove) -> CardPublishResponse:
        self._require_redis()
        event = CardEvent(
            action="remove",
            user_id=data.user_id,
            product_id=data.product_id,
        )
        channel = await self._publish(event)
        await self._wait_applied(event.event_id)
        card = await self.get_card(data.user_id)
        return CardPublishResponse(
            event_id=event.event_id,
            channel=channel,
            card=card,
        )

    async def clear_card(self, user_id: int) -> CardPublishResponse:
        self._require_redis()
        event = CardEvent(action="clear", user_id=user_id)
        channel = await self._publish(event)
        await self._wait_applied(event.event_id)
        card = await self.get_card(user_id)
        return CardPublishResponse(
            event_id=event.event_id,
            channel=channel,
            card=card,
        )

    async def get_card(self, user_id: int) -> CardResponse:
        self._require_redis()
        return await self.store.get(user_id)

    async def checkout(self, user_id: int) -> list[PurchaseResponse]:
        """
        Buy everything currently in the Card.

        Card logic stops here — actual purchase pipeline lives in PurchaseService.
        """
        self._require_redis()
        card = await self.get_card(user_id)
        if not card.items:
            raise HTTPException(status_code=400, detail="Card is empty")

        if self.purchase_creator is None:
            raise HTTPException(status_code=503, detail="Purchase service unavailable")
        results: list[PurchaseResponse] = []
        for item in card.items:
            purchase = await self.purchase_creator.create_purchase(
                PurchaseCreate(
                    user_id=user_id,
                    product_id=item.product_id,
                    amount=item.amount,
                )
            )
            results.append(purchase)

        await self.clear_card(user_id)
        logger.info(
            "Checkout complete user=%s purchases=%s",
            user_id,
            [p.id for p in results],
        )
        return results

    async def _publish(self, event: CardEvent) -> str:
        channel = await self.publisher.publish(event)
        logger.info("Published CardEvent action=%s event_id=%s", event.action, event.event_id)
        return channel

    async def _wait_applied(self, event_id: str, timeout_s: float = 2.0) -> None:
        """Poll until the pub/sub subscriber marks the event as applied."""
        try:
            await self.completion.wait_applied(event_id, timeout_s)
        except TimeoutError as exc:
            raise HTTPException(
                status_code=504,
                detail="Card event subscriber did not apply the event in time",
            ) from exc

    def _require_redis(self) -> None:
        if self.store is None or self.publisher is None or self.completion is None:
            raise HTTPException(status_code=503, detail="Redis unavailable — Card needs pub/sub")
