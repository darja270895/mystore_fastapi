"""
HTTP layer for purchases / inventory / notifications.

Also exposes SSE live events fed by Redis Pub/Sub.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from backend.dependencies import get_purchase_service
from backend.purchases.purchase_schemas import (
    NotificationResponse,
    PurchaseCreate,
    PurchaseResponse,
    StockMovementResponse,
)
from backend.purchases.purchase_service import PurchaseService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/purchases", tags=["Purchases"])


@router.post("/", response_model=PurchaseResponse, status_code=201)
async def create_purchase(
    data: PurchaseCreate,
    service: PurchaseService = Depends(get_purchase_service),
):
    """
    Full async purchase pipeline:
    rate-limit → concurrent validation → lock → DB → stream/pubsub/zset.
    """
    return await service.create_purchase(data)


@router.get("/", response_model=list[PurchaseResponse])
async def list_purchases(service: PurchaseService = Depends(get_purchase_service)):
    return await service.list_purchases()


@router.get("/recent", response_model=list[dict])
async def recent_purchases(service: PurchaseService = Depends(get_purchase_service)):
    """Recent-purchase feed — no SQL query."""
    return await service.recent_purchases()


@router.get("/stock-movements", response_model=list[StockMovementResponse])
async def list_stock_movements(
    product_id: int | None = None,
    service: PurchaseService = Depends(get_purchase_service),
):
    return await service.list_stock_movements(product_id=product_id)


@router.get(
    "/notifications/{user_id}",
    response_model=list[NotificationResponse],
)
async def list_notifications(
    user_id: int,
    service: PurchaseService = Depends(get_purchase_service),
):
    """Rows written by the background Stream consumer after each purchase."""
    return await service.list_notifications(user_id)
