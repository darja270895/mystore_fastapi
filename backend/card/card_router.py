"""
HTTP layer for the shopping Card (Redis Pub/Sub).

Card endpoints only publish / read Redis state.
Buying from the Card triggers PurchaseService via CardService.checkout.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from backend.card.card_ports import CardEventStream
from backend.card.card_schemas import (
    CardAdd,
    CardPublishResponse,
    CardRemove,
    CardResponse,
)
from backend.card.card_service import CardService
from backend.dependencies import get_card_event_stream, get_card_service
from backend.purchases.purchase_schemas import PurchaseResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/card", tags=["Card"])


@router.post("/add", response_model=CardPublishResponse, status_code=201)
async def add_to_card(
    data: CardAdd,
    service: CardService = Depends(get_card_service),
):
    """Publish CardEvent(action=add) → subscriber stores product in Redis HASH."""
    return await service.add_item(data)


@router.post("/remove", response_model=CardPublishResponse)
async def remove_from_card(
    data: CardRemove,
    service: CardService = Depends(get_card_service),
):
    return await service.remove_item(data)


@router.post("/clear/{user_id}", response_model=CardPublishResponse)
async def clear_card(
    user_id: int,
    service: CardService = Depends(get_card_service),
):
    return await service.clear_card(user_id)


@router.get("/events/live")
async def live_card_events(
    request: Request,
    event_stream: CardEventStream | None = Depends(get_card_event_stream),
):
    """SSE stream backed by a dedicated subscriber from the shared Redis pool."""

    async def event_generator():
        if event_stream is None:
            yield _sse("error", {"detail": "Redis unavailable"})
            return

        yield _sse("ready", {"stream": "card"})
        async for data in event_stream.messages():
            if await request.is_disconnected():
                break
            yield _sse("ping", {"ok": True}) if data is None else _sse("card", data)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{user_id}", response_model=CardResponse)
async def get_card(
    user_id: int,
    service: CardService = Depends(get_card_service),
):
    """Read Card from Redis HASH (written by the pub/sub subscriber)."""
    return await service.get_card(user_id)


@router.post("/checkout/{user_id}", response_model=list[PurchaseResponse], status_code=201)
async def checkout_card(
    user_id: int,
    service: CardService = Depends(get_card_service),
):
    """
    Buy all items in the Card.

    Internally calls PurchaseService for each line item, then clears the Card.
    """
    return await service.checkout(user_id)


def _sse(event: str, data: str | dict) -> str:
    payload = data if isinstance(data, str) else json.dumps(data)
    return f"event: {event}\ndata: {payload}\n\n"
