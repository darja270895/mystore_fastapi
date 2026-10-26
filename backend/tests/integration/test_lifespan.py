"""Lifespan integration tests: real pool, real leader election, real listener."""

import asyncio

import pytest
import redis.asyncio as asyncredis
from sqlalchemy import select

from backend import models
from backend.card.card_events import CardEvent
from backend.config import settings
from backend.main import app, main_lifespan
from backend.purchases.purchase_events import PurchaseEvent
from backend.redis_app.adapters import build_redis_adapters
from backend.redis_app.redis_lifespan import redis_lifespan
from backend.tests.conftest import TEST_REDIS_DB


@pytest.fixture
async def redis_enabled(monkeypatch, redis_client):
    """Point the lifespan at the test database index (flushed by `redis_client`)."""
    monkeypatch.setattr(settings, "USE_REDIS", True)
    monkeypatch.setattr(settings, "REDIS_DB", TEST_REDIS_DB)


async def test_lifespan_exposes_adapters_and_stops_its_listener(redis_enabled):
    async with redis_lifespan(app):
        assert app.state.redis_adapters is not None
        assert await app.state.redis.ping() is True
        assert app.state.pubsub_task.done() is False

    assert app.state.pubsub_task.done() is True


async def test_card_events_are_applied_by_the_lifespan_listener(redis_enabled):
    async with redis_lifespan(app):
        adapters = app.state.redis_adapters
        event = CardEvent(
            action="add", user_id=1, product_id=5, amount=2, product_name="Book"
        )

        await adapters.card_publisher.publish(event)
        await adapters.event_completion.wait_applied(event.event_id, timeout_s=3)

        assert (await adapters.card_store.get(1)).total_items == 2


async def test_only_one_worker_becomes_stream_consumer_leader(redis_enabled):
    async with redis_lifespan(app):
        rival = asyncredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=TEST_REDIS_DB,
            decode_responses=True,
        )
        try:
            rival_adapters = build_redis_adapters(rival)
            assert await rival_adapters.consumer_leadership.acquire("rival") is False
        finally:
            await rival.aclose()


async def test_leader_lock_is_released_on_shutdown(redis_enabled, redis_client):
    async with redis_lifespan(app):
        assert await redis_client.exists(settings.CONSUMER_LEADER_LOCK_KEY) == 1

    assert await redis_client.exists(settings.CONSUMER_LEADER_LOCK_KEY) == 0


async def test_main_lifespan_skips_redis_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "USE_REDIS", False)
    monkeypatch.delattr(app.state, "redis_adapters", raising=False)

    async with main_lifespan(app):
        assert getattr(app.state, "redis_adapters", None) is None


async def test_streamed_purchase_event_becomes_a_notification_row(
    redis_enabled, session_factory
):
    """End of the async pipeline: XADD in a request → consumer → Notification."""
    async with session_factory() as session:
        user = models.User(name="Buyer", email="lifespan@example.com")
        session.add(user)
        await session.commit()
        await session.refresh(user)

    async with redis_lifespan(app):
        # The consumer reads from "$", so let it issue its first XREAD first.
        await asyncio.sleep(0.5)

        await app.state.redis_adapters.purchase_events.dispatch(
            PurchaseEvent(
                purchase_id=1,
                user_id=user.id,
                product_id=1,
                amount=1,
                product_name="Lifespan",
                total_price=10.0,
            )
        )

        notification = await wait_for_notification(session_factory, user.id)

    assert notification.kind == "purchase_confirmed"
    assert '"product_name":"Lifespan"' in notification.payload.replace(" ", "")


async def wait_for_notification(session_factory, user_id: int, timeout: float = 8.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        async with session_factory() as session:
            result = await session.execute(
                select(models.Notification).where(models.Notification.user_id == user_id)
            )
            notification = result.scalars().first()
            if notification is not None:
                return notification
        await asyncio.sleep(0.05)
    raise AssertionError("stream consumer never wrote a notification")
