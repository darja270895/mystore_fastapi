"""PurchaseService unit tests: rate limit, locking, stock rules, side effects."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend import models
from backend.purchases.purchase_schemas import PurchaseCreate, PurchaseResponse
from backend.purchases.purchase_service import PurchaseService
from backend.tests.fakes import (
    InMemoryPurchaseCoordinator,
    InMemoryPurchaseEvents,
    InMemoryRecentPurchaseFeed,
)


def make_user(user_id: int = 1):
    user = models.User(name="Buyer", email="buyer@example.com")
    user.id = user_id
    return user


def make_product(product_id: int = 2, stock: int = 5, price: float = 10.0):
    product = models.Product(name="Mouse", stock=stock, price=price)
    product.id = product_id
    return product


def make_purchase(purchase_id: int = 3, amount: int = 1):
    from datetime import datetime, timezone

    purchase = models.Purchase(user_id=1, product_id=2, amount=amount)
    purchase.id = purchase_id
    purchase.created_at = datetime.now(timezone.utc)
    return purchase


def build_service(
    coordinator=None,
    events=None,
    recent_feed=None,
    *,
    product=None,
    user=None,
) -> PurchaseService:
    service = PurchaseService(
        db_session=AsyncMock(),
        coordinator=coordinator,
        events=events,
        recent_feed=recent_feed,
    )
    service.db = AsyncMock()
    service.db.get_product.return_value = product if product is not None else make_product()
    service.db.create_purchase.return_value = make_purchase()
    # Concurrent user+product preload is covered by the DB integration tests.
    service._load_user_and_product = AsyncMock(
        return_value=(
            user if user is not None else make_user(),
            product if product is not None else make_product(),
        )
    )
    return service


async def test_create_purchase_happy_path_dispatches_event_and_releases_lock():
    coordinator = InMemoryPurchaseCoordinator()
    feed = InMemoryRecentPurchaseFeed()
    events = InMemoryPurchaseEvents(feed=feed)
    service = build_service(coordinator, events, feed)

    result = await service.create_purchase(PurchaseCreate(user_id=1, product_id=2, amount=2))

    assert isinstance(result, PurchaseResponse)
    service.db.decrement_stock.assert_awaited_once()
    service.db.create_stock_movement.assert_awaited_once()
    service.db_session.commit.assert_awaited_once()

    assert len(events.dispatched) == 1
    event = events.dispatched[0]
    assert event.amount == 2
    assert event.total_price == 20.0
    assert coordinator.locks == {}  # released in the finally block


async def test_create_purchase_rejects_when_rate_limited():
    coordinator = InMemoryPurchaseCoordinator(limit=1)
    service = build_service(coordinator, InMemoryPurchaseEvents())

    await service.create_purchase(PurchaseCreate(user_id=1, product_id=2, amount=1))

    with pytest.raises(HTTPException) as exc_info:
        await service.create_purchase(PurchaseCreate(user_id=1, product_id=2, amount=1))

    assert exc_info.value.status_code == 429


async def test_create_purchase_conflicts_when_stock_lock_is_taken():
    coordinator = InMemoryPurchaseCoordinator(lock_available=False)
    service = build_service(coordinator, InMemoryPurchaseEvents())

    with pytest.raises(HTTPException) as exc_info:
        await service.create_purchase(PurchaseCreate(user_id=1, product_id=2, amount=1))

    assert exc_info.value.status_code == 409


async def test_create_purchase_rejects_insufficient_stock_and_releases_lock():
    coordinator = InMemoryPurchaseCoordinator()
    service = build_service(coordinator, InMemoryPurchaseEvents(), product=make_product(stock=1))

    with pytest.raises(HTTPException) as exc_info:
        await service.create_purchase(PurchaseCreate(user_id=1, product_id=2, amount=5))

    assert exc_info.value.status_code == 400
    assert "Insufficient stock" in exc_info.value.detail
    assert len(coordinator.released) == 1
    assert coordinator.locks == {}


async def test_create_purchase_404_when_product_disappears_inside_lock():
    coordinator = InMemoryPurchaseCoordinator()
    service = build_service(coordinator, InMemoryPurchaseEvents())
    service.db.get_product.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await service.create_purchase(PurchaseCreate(user_id=1, product_id=2, amount=1))

    assert exc_info.value.status_code == 404


async def test_create_purchase_degrades_without_redis_ports():
    service = build_service(coordinator=None, events=None)

    result = await service.create_purchase(PurchaseCreate(user_id=1, product_id=2, amount=1))

    assert isinstance(result, PurchaseResponse)


async def test_recent_purchases_returns_empty_without_feed():
    service = build_service()

    assert await service.recent_purchases() == []


async def test_recent_purchases_reads_feed_port():
    feed = AsyncMock()
    feed.list_recent.return_value = [{"purchase_id": 1}]
    service = build_service(recent_feed=feed)

    assert await service.recent_purchases() == [{"purchase_id": 1}]
    feed.list_recent.assert_awaited_once_with(limit=100)


async def test_read_queries_delegate_to_repository():
    service = build_service()
    service.db.get_all.return_value = [make_purchase()]
    service.db.list_stock_movements.return_value = ["movement"]
    service.db.list_notifications.return_value = ["notification"]

    assert len(await service.list_purchases()) == 1
    assert await service.list_stock_movements(product_id=2) == ["movement"]
    assert await service.list_notifications(1) == ["notification"]
    service.db.list_stock_movements.assert_awaited_once_with(product_id=2)
