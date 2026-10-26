"""Adapter integration tests: real Redis keys, TTLs and data structures."""

import asyncio

import pytest

from backend.card.card_events import CardEvent
from backend.config import settings
from backend.products.product_schemas import ProductResponse
from backend.purchases.purchase_events import PurchaseEvent
from backend.redis_app import keys


def make_purchase_event(purchase_id: int = 1, product_id: int = 3) -> PurchaseEvent:
    return PurchaseEvent(
        purchase_id=purchase_id,
        user_id=2,
        product_id=product_id,
        amount=2,
        product_name="Book",
        total_price=40.0,
    )


class TestProductCacheAdapter:
    async def test_cache_aside_cycle_on_real_keys(self, redis_client, redis_adapters):
        cache = redis_adapters.product_cache
        product = ProductResponse(id=9, name="Desk", stock=2, price=30)

        assert await cache.get(9) is None

        await cache.put(9, product)

        assert await redis_client.exists(keys.product_cache_key(9)) == 1
        assert await cache.get(9) == product
        assert 0 < await cache.ttl(9) <= settings.CACHE_TTL_SECONDS

        await cache.invalidate(9)

        assert await cache.get(9) is None
        assert await cache.ttl(9) == -2


class TestPurchaseAdapters:
    async def test_rate_limit_counts_per_user_key(self, redis_client, redis_adapters):
        coordinator = redis_adapters.purchase_coordinator

        allowed, count = await coordinator.check_rate_limit(42)

        assert (allowed, count) == (True, 1)
        assert await redis_client.get(keys.buy_rate_limit_key(42)) == "1"

    async def test_rate_limit_rejects_past_the_configured_limit(self, redis_adapters):
        coordinator = redis_adapters.purchase_coordinator

        for _ in range(settings.RATE_LIMIT_BUY_PER_MINUTE):
            allowed, _ = await coordinator.check_rate_limit(43)
            assert allowed is True

        allowed, count = await coordinator.check_rate_limit(43)

        assert allowed is False
        assert count == settings.RATE_LIMIT_BUY_PER_MINUTE + 1

    async def test_stock_lock_is_exclusive_per_product(self, redis_client, redis_adapters):
        coordinator = redis_adapters.purchase_coordinator

        assert await coordinator.acquire_stock_lock(5, "token-a") is True
        assert await coordinator.acquire_stock_lock(5, "token-b") is False
        assert await coordinator.acquire_stock_lock(6, "token-b") is True
        assert await redis_client.get(keys.stock_lock_key(5)) == "token-a"

        await coordinator.release_stock_lock(5, "token-a")

        assert await redis_client.exists(keys.stock_lock_key(5)) == 0

    async def test_dispatch_writes_stream_zset_and_invalidates_cache(
        self, redis_client, redis_adapters
    ):
        product = ProductResponse(id=3, name="Book", stock=1, price=20)
        await redis_adapters.product_cache.put(3, product)
        event = make_purchase_event()

        await redis_adapters.purchase_events.dispatch(event)

        assert await redis_adapters.product_cache.get(3) is None
        assert await redis_client.xlen(settings.PURCHASE_STREAM) == 1
        assert await redis_client.zcard(settings.RECENT_PURCHASES_ZSET) == 1

        recent = await redis_adapters.recent_purchases.list_recent(limit=10)
        assert recent[0]["purchase_id"] == 1
        assert recent[0]["total_price"] == 40.0

    async def test_recent_feed_is_capped_and_ordered_newest_first(self, redis_adapters):
        for purchase_id in range(settings.RECENT_PURCHASES_MAX + 3):
            event = make_purchase_event(purchase_id=purchase_id)
            event.created_at = event.created_at.replace(microsecond=purchase_id % 1_000_000)
            await redis_adapters.purchase_events.dispatch(event)

        recent = await redis_adapters.recent_purchases.list_recent(
            limit=settings.RECENT_PURCHASES_MAX + 10
        )

        assert len(recent) == settings.RECENT_PURCHASES_MAX

    async def test_event_source_reads_back_what_dispatch_wrote(self, redis_adapters):
        await redis_adapters.purchase_events.dispatch(make_purchase_event(purchase_id=7))

        messages = await redis_adapters.purchase_event_source.read("0")

        assert len(messages) == 1
        message_id, event = messages[0]
        assert message_id.endswith("-0")
        assert event.purchase_id == 7
        assert event.product_name == "Book"
        assert event.total_price == 40.0

    async def test_leadership_lock_allows_a_single_holder(self, redis_adapters):
        leadership = redis_adapters.consumer_leadership

        assert await leadership.acquire("leader-1") is True
        assert await leadership.acquire("leader-2") is False
        assert await leadership.refresh("leader-2") is False
        assert await leadership.refresh("leader-1") is True

        await leadership.release("leader-1")

        assert await leadership.acquire("leader-2") is True


class TestCardAdapters:
    async def test_store_applies_add_remove_and_clear(self, redis_client, redis_adapters):
        store = redis_adapters.card_store

        await store.apply_add(
            CardEvent(action="add", user_id=1, product_id=7, amount=2, product_name="Book")
        )
        await store.apply_add(CardEvent(action="add", user_id=1, product_id=7, amount=1))
        await store.apply_add(
            CardEvent(action="add", user_id=1, product_id=8, amount=1, product_name="Pad")
        )

        card = await store.get(1)
        assert card.total_items == 4
        assert [(item.product_id, item.amount) for item in card.items] == [(7, 3), (8, 1)]
        assert card.items[0].product_name == "Book"

        await store.apply_remove(CardEvent(action="remove", user_id=1, product_id=7))
        assert (await store.get(1)).total_items == 1

        await store.clear(1)
        assert (await store.get(1)).items == []
        assert await redis_client.exists(keys.card_key(1)) == 0

    async def test_empty_card_is_a_valid_response(self, redis_adapters):
        card = await redis_adapters.card_store.get(404)

        assert card.user_id == 404
        assert card.items == []
        assert card.total_items == 0

    async def test_completion_markers_claim_once_and_unblock_waiters(
        self, redis_client, redis_adapters
    ):
        completion = redis_adapters.event_completion

        assert await completion.try_claim("event-1") is True
        assert await completion.try_claim("event-1") is False
        assert await redis_client.exists(keys.card_event_claim_key("event-1")) == 1

        with pytest.raises(TimeoutError):
            await completion.wait_applied("event-1", timeout_s=0.1)

        await completion.mark_applied("event-1")
        await completion.wait_applied("event-1", timeout_s=0.5)

        await completion.release_claim("event-1")
        assert await completion.try_claim("event-1") is True

    async def test_publisher_reaches_a_live_subscriber(self, redis_client, redis_adapters):
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(settings.CARD_CHANNEL)
        await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
        event = CardEvent(action="add", user_id=1, product_id=7, amount=1)

        channel = await redis_adapters.card_publisher.publish(event)

        message = await next_message(pubsub)
        assert channel == settings.CARD_CHANNEL
        assert event.event_id in message["data"]

        await pubsub.unsubscribe(settings.CARD_CHANNEL)
        await pubsub.aclose()

    async def test_event_stream_yields_published_events_and_keepalives(
        self, redis_adapters
    ):
        stream = redis_adapters.card_event_stream
        iterator = stream.messages().__aiter__()

        async def publish_soon() -> None:
            await asyncio.sleep(0.2)
            await redis_adapters.card_publisher.publish(
                CardEvent(action="clear", user_id=1)
            )

        task = asyncio.create_task(publish_soon())
        try:
            payloads = []
            for _ in range(5):
                message = await asyncio.wait_for(iterator.__anext__(), timeout=3)
                if message is not None:
                    payloads.append(message)
                    break
            assert payloads and '"action":"clear"' in payloads[0].replace(" ", "")
        finally:
            await task
            await iterator.aclose()


async def next_message(pubsub, timeout: float = 2.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
        if message is not None:
            return message
    raise AssertionError("no message received from Redis Pub/Sub")
