"""CardService unit tests: publish/apply handshake, validation, checkout."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend import models
from backend.card.card_schemas import CardAdd, CardRemove
from backend.card.card_service import CardService
from backend.purchases.purchase_schemas import PurchaseResponse
from backend.tests.fakes import (
    InMemoryCardStore,
    InMemoryEventCompletion,
    LoopbackCardEventPublisher,
)
from backend.redis_app.redis_pub_sub_events import RedisPubSub


def make_user(user_id: int = 1):
    user = models.User(name="Buyer", email="buyer@example.com")
    user.id = user_id
    return user


def make_product(product_id: int = 2, name: str = "Mouse"):
    product = models.Product(name=name, stock=5, price=10)
    product.id = product_id
    return product


@pytest.fixture
def card_ports():
    store = InMemoryCardStore()
    completion = InMemoryEventCompletion()
    handler = RedisPubSub(store=store, completion=completion, channel="channel:card")
    publisher = LoopbackCardEventPublisher(handler)
    return store, completion, publisher


@pytest.fixture
def service(card_ports) -> CardService:
    store, completion, publisher = card_ports
    service = CardService(
        db_session=AsyncMock(),
        store=store,
        publisher=publisher,
        completion=completion,
        purchase_creator=AsyncMock(),
    )
    service.db = AsyncMock()
    service.db.get_user.return_value = make_user()
    service.db.get_product.return_value = make_product()
    return service


async def test_add_item_publishes_event_and_returns_updated_card(service):
    response = await service.add_item(CardAdd(user_id=1, product_id=2, amount=3))

    assert response.channel == "channel:card"
    assert response.card.total_items == 3
    assert response.card.items[0].product_name == "Mouse"
    assert response.event_id


async def test_add_item_validates_user_and_product(service):
    service.db.get_user.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.add_item(CardAdd(user_id=1, product_id=2, amount=1))
    assert exc_info.value.status_code == 404

    service.db.get_user.return_value = make_user()
    service.db.get_product.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.add_item(CardAdd(user_id=1, product_id=2, amount=1))
    assert exc_info.value.status_code == 404


async def test_remove_item_drops_product_from_card(service):
    await service.add_item(CardAdd(user_id=1, product_id=2, amount=2))

    response = await service.remove_item(CardRemove(user_id=1, product_id=2))

    assert response.card.items == []
    assert response.card.total_items == 0


async def test_clear_card_empties_all_items(service):
    await service.add_item(CardAdd(user_id=1, product_id=2, amount=2))

    response = await service.clear_card(1)

    assert response.card.total_items == 0


async def test_wait_applied_timeout_maps_to_504(service, card_ports):
    _, completion, _ = card_ports
    completion.wait_applied = AsyncMock(side_effect=TimeoutError("not applied"))

    with pytest.raises(HTTPException) as exc_info:
        await service.add_item(CardAdd(user_id=1, product_id=2, amount=1))

    assert exc_info.value.status_code == 504


async def test_card_endpoints_require_redis_ports():
    service = CardService(db_session=AsyncMock(), store=None, publisher=None, completion=None)

    for coroutine in (
        service.get_card(1),
        service.add_item(CardAdd(user_id=1, product_id=2, amount=1)),
        service.clear_card(1),
        service.checkout(1),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await coroutine
        assert exc_info.value.status_code == 503


async def test_checkout_rejects_empty_card(service):
    with pytest.raises(HTTPException) as exc_info:
        await service.checkout(1)

    assert exc_info.value.status_code == 400


async def test_checkout_requires_purchase_creator(service):
    await service.add_item(CardAdd(user_id=1, product_id=2, amount=1))
    service.purchase_creator = None

    with pytest.raises(HTTPException) as exc_info:
        await service.checkout(1)

    assert exc_info.value.status_code == 503


async def test_checkout_buys_each_line_item_then_clears_card(service):
    from datetime import datetime, timezone

    service.db.get_product.return_value = make_product(product_id=2)
    await service.add_item(CardAdd(user_id=1, product_id=2, amount=2))
    service.db.get_product.return_value = make_product(product_id=3, name="Pad")
    await service.add_item(CardAdd(user_id=1, product_id=3, amount=1))

    service.purchase_creator.create_purchase.side_effect = [
        PurchaseResponse(
            id=10, user_id=1, product_id=2, amount=2, created_at=datetime.now(timezone.utc)
        ),
        PurchaseResponse(
            id=11, user_id=1, product_id=3, amount=1, created_at=datetime.now(timezone.utc)
        ),
    ]

    results = await service.checkout(1)

    assert [purchase.id for purchase in results] == [10, 11]
    assert service.purchase_creator.create_purchase.await_count == 2
    assert (await service.get_card(1)).total_items == 0
