"""Service integration tests: real SQLite, in-memory ports.

These cover the paths that the unit tests stub out — concurrent user/product
loading, stock decrements, the stock-movement ledger and cache invalidation.
"""

import asyncio
import json

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from backend import models
from backend.card.card_schemas import CardAdd
from backend.card.card_service import CardService
from backend.products.product_schemas import ProductCreate
from backend.products.product_service import ProductService
from backend.purchases.purchase_db_interface import PurchaseDbInterface
from backend.purchases.purchase_schemas import PurchaseCreate
from backend.purchases.purchase_service import PurchaseService
from backend.redis_app.stream_consumer import PurchaseStreamConsumer
from backend.tests.fakes import InMemoryConsumerLeadership, InMemoryPurchaseEventSource


def build_purchase_service(session, adapters) -> PurchaseService:
    return PurchaseService(
        db_session=session,
        coordinator=adapters.purchase_coordinator,
        events=adapters.purchase_events,
        recent_feed=adapters.recent_purchases,
    )


class TestProductServiceWithDatabase:
    async def test_create_then_read_is_served_from_cache(
        self, db_session, fake_adapters
    ):
        service = ProductService(db_session=db_session, cache=fake_adapters.product_cache)

        created = await service.create_product(ProductCreate(name="Desk", stock=4, price=99))
        fetched = await service.get_by_id(created.id)

        assert fetched.name == "Desk"
        assert fake_adapters.product_cache.put_calls == [created.id]

    async def test_cache_miss_reads_the_row_and_warms_the_cache(
        self, db_session, fake_adapters
    ):
        service = ProductService(db_session=db_session, cache=fake_adapters.product_cache)
        created = await service.create_product(ProductCreate(name="Desk", stock=4, price=99))
        fake_adapters.product_cache.values.clear()

        fetched = await service.get_by_id(created.id)

        assert fetched.stock == 4
        assert created.id in fake_adapters.product_cache.values

    async def test_delete_removes_row_and_cache_entry(self, db_session, fake_adapters):
        service = ProductService(db_session=db_session, cache=fake_adapters.product_cache)
        created = await service.create_product(ProductCreate(name="Desk", stock=1, price=5))

        await service.delete_product(created.id)

        assert fake_adapters.product_cache.invalidated == [created.id]
        with pytest.raises(HTTPException):
            await service.get_by_id(created.id)

    async def test_duplicate_name_is_rejected_against_a_real_row(
        self, db_session, fake_adapters
    ):
        service = ProductService(db_session=db_session, cache=fake_adapters.product_cache)
        await service.create_product(ProductCreate(name="Desk", stock=1, price=5))

        with pytest.raises(HTTPException) as exc_info:
            await service.create_product(ProductCreate(name="Desk", stock=2, price=6))

        assert exc_info.value.status_code == 409


class TestPurchaseServiceWithDatabase:
    async def test_purchase_writes_rows_and_updates_projections(
        self, db_session, session_factory, seed, fake_adapters
    ):
        user, product = await seed(stock=10, price=25)
        service = build_purchase_service(db_session, fake_adapters)

        purchase = await service.create_purchase(
            PurchaseCreate(user_id=user.id, product_id=product.id, amount=3)
        )

        async with session_factory() as session:
            repository = PurchaseDbInterface(session)
            assert (await repository.get_by_id(purchase.id)).amount == 3
            assert (await repository.get_product(product.id)).stock == 7
            movements = await repository.list_stock_movements(product_id=product.id)
            assert [(row.delta, row.reason) for row in movements] == [(-3, "purchase")]

        event = fake_adapters.purchase_events.dispatched[0]
        assert event.total_price == 75.0
        assert await service.recent_purchases() == [json.loads(event.model_dump_json())]

    async def test_unknown_user_or_product_is_rejected_before_any_write(
        self, db_session, seed, fake_adapters
    ):
        user, product = await seed()
        service = build_purchase_service(db_session, fake_adapters)

        with pytest.raises(HTTPException) as exc_info:
            await service.create_purchase(
                PurchaseCreate(user_id=user.id + 999, product_id=product.id, amount=1)
            )
        assert exc_info.value.status_code == 404

        with pytest.raises(HTTPException) as exc_info:
            await service.create_purchase(
                PurchaseCreate(user_id=user.id, product_id=product.id + 999, amount=1)
            )
        assert exc_info.value.status_code == 404

        assert fake_adapters.purchase_events.dispatched == []

    async def test_insufficient_stock_leaves_the_row_untouched(
        self, db_session, session_factory, seed, fake_adapters
    ):
        user, product = await seed(stock=2)
        service = build_purchase_service(db_session, fake_adapters)

        with pytest.raises(HTTPException) as exc_info:
            await service.create_purchase(
                PurchaseCreate(user_id=user.id, product_id=product.id, amount=5)
            )

        assert exc_info.value.status_code == 400
        async with session_factory() as session:
            assert (await PurchaseDbInterface(session).get_product(product.id)).stock == 2

    async def test_purchase_is_rejected_while_another_holder_owns_the_stock_lock(
        self, db_session, seed, fake_adapters
    ):
        user, product = await seed(stock=10)
        await fake_adapters.purchase_coordinator.acquire_stock_lock(product.id, "other-worker")
        service = build_purchase_service(db_session, fake_adapters)

        with pytest.raises(HTTPException) as exc_info:
            await service.create_purchase(
                PurchaseCreate(user_id=user.id, product_id=product.id, amount=1)
            )

        assert exc_info.value.status_code == 409
        assert fake_adapters.purchase_coordinator.locks[product.id] == "other-worker"

    async def test_concurrent_buyers_never_oversell(
        self, session_factory, seed, fake_adapters
    ):
        user, product = await seed(stock=3)

        async def buy() -> int:
            async with session_factory() as session:
                service = build_purchase_service(session, fake_adapters)
                try:
                    await service.create_purchase(
                        PurchaseCreate(user_id=user.id, product_id=product.id, amount=1)
                    )
                    return 200
                except HTTPException as error:
                    return error.status_code

        results = await asyncio.gather(*(buy() for _ in range(5)))

        confirmed = results.count(200)
        assert confirmed <= 3
        assert set(results) <= {200, 409, 400}
        async with session_factory() as session:
            product_row = await PurchaseDbInterface(session).get_product(product.id)
            assert product_row.stock == 3 - confirmed

    async def test_rate_limit_blocks_the_sixth_purchase(
        self, db_session, seed, fake_adapters
    ):
        user, product = await seed(stock=100)
        fake_adapters.purchase_coordinator.limit = 2
        service = build_purchase_service(db_session, fake_adapters)

        for _ in range(2):
            await service.create_purchase(
                PurchaseCreate(user_id=user.id, product_id=product.id, amount=1)
            )

        with pytest.raises(HTTPException) as exc_info:
            await service.create_purchase(
                PurchaseCreate(user_id=user.id, product_id=product.id, amount=1)
            )

        assert exc_info.value.status_code == 429


class TestStreamConsumerWithDatabase:
    async def test_consumer_persists_notifications_for_streamed_events(
        self, session_factory, seed, fake_adapters
    ):
        user, product = await seed(stock=5, price=25)
        async with session_factory() as session:
            service = build_purchase_service(session, fake_adapters)
            await service.create_purchase(
                PurchaseCreate(user_id=user.id, product_id=product.id, amount=2)
            )

        event = fake_adapters.purchase_events.dispatched[0]
        consumer = PurchaseStreamConsumer(
            source=InMemoryPurchaseEventSource([event]),
            leadership=InMemoryConsumerLeadership(),
            leader_token="token-1",
        )

        async with consumer:
            await wait_for_notification(session_factory, user.id)

        async with session_factory() as session:
            notifications = await PurchaseDbInterface(session).list_notifications(user.id)

        assert notifications[0].kind == "purchase_confirmed"
        assert str(event.purchase_id) in notifications[0].payload
        assert notifications[0].is_read is False


class TestCardServiceWithDatabase:
    async def test_card_uses_real_product_names(self, db_session, seed, fake_adapters):
        user, product = await seed(product_name="Keyboard")
        service = CardService(
            db_session=db_session,
            store=fake_adapters.card_store,
            publisher=fake_adapters.card_publisher,
            completion=fake_adapters.event_completion,
            purchase_creator=build_purchase_service(db_session, fake_adapters),
        )

        response = await service.add_item(
            CardAdd(user_id=user.id, product_id=product.id, amount=2)
        )

        assert response.card.items[0].product_name == "Keyboard"

    async def test_checkout_creates_purchases_and_drains_the_card(
        self, db_session, session_factory, seed, fake_adapters
    ):
        user, product = await seed(stock=5, price=25)
        service = CardService(
            db_session=db_session,
            store=fake_adapters.card_store,
            publisher=fake_adapters.card_publisher,
            completion=fake_adapters.event_completion,
            purchase_creator=build_purchase_service(db_session, fake_adapters),
        )
        await service.add_item(CardAdd(user_id=user.id, product_id=product.id, amount=2))

        purchases = await service.checkout(user.id)

        assert [purchase.amount for purchase in purchases] == [2]
        assert (await service.get_card(user.id)).total_items == 0
        async with session_factory() as session:
            assert (await PurchaseDbInterface(session).get_product(product.id)).stock == 3


async def wait_for_notification(session_factory, user_id: int, timeout: float = 3.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        async with session_factory() as session:
            result = await session.execute(
                select(models.Notification).where(models.Notification.user_id == user_id)
            )
            if result.scalars().first() is not None:
                return
        await asyncio.sleep(0.02)
    raise AssertionError("notification was never written")
