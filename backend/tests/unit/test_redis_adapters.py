"""Adapter unit tests: adapters own key names, TTLs and payload shapes.

The Redis command layer is mocked here; the real commands are exercised by the
integration tests.
"""

import json
from unittest.mock import AsyncMock

import pytest

from backend.card.card_events import CardEvent
from backend.config import settings
from backend.products.product_schemas import ProductResponse
from backend.purchases.purchase_events import PurchaseEvent
from backend.redis_app import keys
from backend.redis_app.adapters.card import (
    RedisCardEventPublisher,
    RedisCardEventStream,
    RedisCardStore,
    RedisEventCompletion,
)
from backend.redis_app.adapters.product_cache import RedisProductCache
from backend.redis_app.adapters.purchase import (
    RedisConsumerLeadership,
    RedisPurchaseCoordinator,
    RedisPurchaseEvents,
    RedisPurchaseEventSource,
    RedisRecentPurchaseFeed,
)


def make_purchase_event() -> PurchaseEvent:
    return PurchaseEvent(
        purchase_id=1,
        user_id=2,
        product_id=3,
        amount=2,
        product_name="Book",
        total_price=40.0,
    )


class TestProductCacheAdapter:
    async def test_put_owns_key_and_ttl_policy(self):
        cache = AsyncMock()
        product = ProductResponse(id=5, name="Book", stock=3, price=20)

        await RedisProductCache(cache).put(5, product)

        cache.set_value.assert_awaited_once_with(
            keys.product_cache_key(5),
            product.model_dump(mode="json"),
            ex=settings.CACHE_TTL_SECONDS,
        )

    async def test_get_rebuilds_projection_from_stored_json(self):
        cache = AsyncMock()
        cache.get_value.return_value = {"id": 5, "name": "Book", "stock": 3, "price": 20.0}

        product = await RedisProductCache(cache).get(5)

        assert product == ProductResponse(id=5, name="Book", stock=3, price=20)
        cache.get_value.assert_awaited_once_with(keys.product_cache_key(5))

    async def test_get_returns_none_on_cache_miss(self):
        cache = AsyncMock()
        cache.get_value.return_value = None

        assert await RedisProductCache(cache).get(5) is None

    async def test_invalidate_and_ttl_target_the_same_key(self):
        cache = AsyncMock()
        cache.ttl_check.return_value = 42
        adapter = RedisProductCache(cache)

        await adapter.invalidate(5)
        assert await adapter.ttl(5) == 42

        cache.delete_value.assert_awaited_once_with(keys.product_cache_key(5))
        cache.ttl_check.assert_awaited_once_with(keys.product_cache_key(5))


class TestPurchaseCoordinatorAdapter:
    async def test_rate_limit_and_lock_keys(self):
        rates = AsyncMock()
        rates.check_rate_limit.return_value = (True, 1)
        locks = AsyncMock()
        locks.acquire_lock.return_value = True
        adapter = RedisPurchaseCoordinator(rates, locks)

        assert await adapter.check_rate_limit(9) == (True, 1)
        assert await adapter.acquire_stock_lock(4, "token") is True

        rates.check_rate_limit.assert_awaited_once_with(
            key=keys.buy_rate_limit_key(9),
            limit=settings.RATE_LIMIT_BUY_PER_MINUTE,
            window_seconds=60,
        )
        locks.acquire_lock.assert_awaited_once_with(
            key=keys.stock_lock_key(4),
            token="token",
            ttl_ms=settings.STOCK_LOCK_TTL_MS,
        )

    async def test_release_passes_the_owning_token(self):
        locks = AsyncMock()

        await RedisPurchaseCoordinator(AsyncMock(), locks).release_stock_lock(4, "token")

        locks.release_lock.assert_awaited_once_with(keys.stock_lock_key(4), "token")


class TestPurchaseEventsAdapter:
    async def test_dispatch_fans_out_to_every_redis_structure(self):
        cache, streams, publisher, zsets = (AsyncMock() for _ in range(4))
        adapter = RedisPurchaseEvents(cache, streams, publisher, zsets)
        event = make_purchase_event()

        await adapter.dispatch(event)

        cache.delete_value.assert_awaited_once_with(keys.product_cache_key(3))

        stream_name, fields = streams.stream_add.await_args.args
        assert stream_name == settings.PURCHASE_STREAM
        assert fields["purchase_id"] == "1"
        assert all(isinstance(value, str) for value in fields.values())

        channel, payload = publisher.publish.await_args.args
        assert channel == settings.PURCHASE_CHANNEL
        assert payload["total_price"] == 40.0

        zsets.zadd_scored.assert_awaited_once_with(
            settings.RECENT_PURCHASES_ZSET,
            member=event.model_dump_json(),
            score=event.created_at.timestamp(),
        )
        zsets.zcard_trim.assert_awaited_once_with(
            settings.RECENT_PURCHASES_ZSET,
            settings.RECENT_PURCHASES_MAX,
        )


class TestRecentPurchaseFeedAdapter:
    async def test_list_recent_decodes_members_newest_first(self):
        zsets = AsyncMock()
        event = make_purchase_event()
        zsets.zrevrange.return_value = [event.model_dump_json()]

        feed = await RedisRecentPurchaseFeed(zsets).list_recent(limit=10)

        assert feed == [json.loads(event.model_dump_json())]
        zsets.zrevrange.assert_awaited_once_with(settings.RECENT_PURCHASES_ZSET, 0, 9)


class TestPurchaseEventSourceAdapter:
    async def test_read_flattens_and_validates_stream_entries(self):
        streams = AsyncMock()
        event = make_purchase_event()
        fields = {key: str(value) for key, value in event.model_dump(mode="json").items()}
        streams.stream_read.return_value = [(settings.PURCHASE_STREAM, [("5-0", fields)])]

        messages = await RedisPurchaseEventSource(streams).read("$")

        assert messages[0][0] == "5-0"
        assert messages[0][1].purchase_id == 1
        streams.stream_read.assert_awaited_once_with(
            stream=settings.PURCHASE_STREAM,
            last_id="$",
            block_ms=2_000,
        )

    async def test_read_returns_empty_list_when_stream_is_idle(self):
        streams = AsyncMock()
        streams.stream_read.return_value = []

        assert await RedisPurchaseEventSource(streams).read("$") == []


class TestConsumerLeadershipAdapter:
    async def test_leadership_uses_a_single_well_known_lock_key(self):
        locks = AsyncMock()
        locks.acquire_lock.return_value = True
        locks.refresh_lock.return_value = True
        adapter = RedisConsumerLeadership(locks)

        assert await adapter.acquire("token") is True
        assert await adapter.refresh("token") is True
        await adapter.release("token")

        locks.acquire_lock.assert_awaited_once_with(
            settings.CONSUMER_LEADER_LOCK_KEY,
            "token",
            ttl_ms=settings.CONSUMER_LEADER_LOCK_TTL_MS,
        )
        locks.refresh_lock.assert_awaited_once_with(
            settings.CONSUMER_LEADER_LOCK_KEY,
            "token",
            ttl_ms=settings.CONSUMER_LEADER_LOCK_TTL_MS,
        )
        locks.release_lock.assert_awaited_once_with(
            settings.CONSUMER_LEADER_LOCK_KEY, "token"
        )


class TestCardStoreAdapter:
    async def test_get_maps_hashes_to_domain_response(self):
        hashes = AsyncMock()
        hashes.hgetall.side_effect = [{"7": "2", "3": "1"}, {"7": "Book"}]

        card = await RedisCardStore(hashes, AsyncMock()).get(11)

        assert card.user_id == 11
        assert card.total_items == 3
        assert [item.product_id for item in card.items] == [3, 7]
        assert card.items[1].product_name == "Book"

    async def test_apply_add_increments_amount_and_stores_name(self):
        hashes = AsyncMock()
        hashes.hincrby.return_value = 3
        event = CardEvent(action="add", user_id=1, product_id=7, amount=2, product_name="Book")

        amount = await RedisCardStore(hashes, AsyncMock()).apply_add(event)

        assert amount == 3
        hashes.hincrby.assert_awaited_once_with(keys.card_key(1), "7", 2)
        hashes.hset.assert_awaited_once_with(
            f"{keys.card_key(1)}:names", "7", "Book"
        )

    async def test_apply_add_without_product_id_is_a_no_op(self):
        hashes = AsyncMock()
        event = CardEvent(action="add", user_id=1, product_id=None, amount=2)

        assert await RedisCardStore(hashes, AsyncMock()).apply_add(event) == 0
        hashes.hincrby.assert_not_awaited()

    async def test_apply_remove_deletes_amount_and_name_fields(self):
        hashes = AsyncMock()
        event = CardEvent(action="remove", user_id=1, product_id=7)

        await RedisCardStore(hashes, AsyncMock()).apply_remove(event)

        assert hashes.hdel.await_args_list[0].args == (keys.card_key(1), "7")
        assert hashes.hdel.await_args_list[1].args == (f"{keys.card_key(1)}:names", "7")

    async def test_clear_drops_both_card_hashes(self):
        cache = AsyncMock()

        await RedisCardStore(AsyncMock(), cache).clear(1)

        assert [call.args[0] for call in cache.delete_value.await_args_list] == [
            keys.card_key(1),
            f"{keys.card_key(1)}:names",
        ]


class TestCardEventPublisherAdapter:
    async def test_publish_returns_the_channel_it_used(self):
        publisher = AsyncMock()
        event = CardEvent(action="add", user_id=1, product_id=7, amount=1)

        channel = await RedisCardEventPublisher(publisher).publish(event)

        assert channel == settings.CARD_CHANNEL
        published_channel, payload = publisher.publish.await_args.args
        assert published_channel == settings.CARD_CHANNEL
        assert payload["event_id"] == event.event_id


class TestEventCompletionAdapter:
    async def test_claim_is_a_set_nx_with_bounded_ttl(self):
        cache = AsyncMock()
        cache.set_nx.return_value = True

        assert await RedisEventCompletion(cache).try_claim("abc") is True

        cache.set_nx.assert_awaited_once_with(
            keys.card_event_claim_key("abc"),
            "1",
            ex=RedisEventCompletion._MARKER_TTL_SECONDS,
        )

    async def test_mark_applied_writes_the_applied_marker(self):
        cache = AsyncMock()

        await RedisEventCompletion(cache).mark_applied("abc")

        cache.set_nx.assert_awaited_once_with(
            keys.card_event_applied_key("abc"),
            "1",
            ex=RedisEventCompletion._MARKER_TTL_SECONDS,
        )

    async def test_release_claim_removes_the_claim_marker(self):
        cache = AsyncMock()

        await RedisEventCompletion(cache).release_claim("abc")

        cache.delete_value.assert_awaited_once_with(keys.card_event_claim_key("abc"))

    async def test_wait_applied_returns_as_soon_as_marker_appears(self):
        cache = AsyncMock()
        cache.exists.side_effect = [False, True]

        await RedisEventCompletion(cache).wait_applied("abc", timeout_s=1.0)

        assert cache.exists.await_count == 2

    async def test_wait_applied_raises_timeout_error(self):
        cache = AsyncMock()
        cache.exists.return_value = False

        with pytest.raises(TimeoutError):
            await RedisEventCompletion(cache).wait_applied("abc", timeout_s=0.05)


class ScriptEnded(Exception):
    """Breaks the adapter's endless subscribe loop once the script is consumed."""


class FakePubSub:
    def __init__(self, messages):
        self._messages = list(messages)
        self.subscribed: list[str] = []
        self.unsubscribed: list[str] = []
        self.closed = False

    async def subscribe(self, channel):
        self.subscribed.append(channel)

    async def get_message(self, ignore_subscribe_messages=False, timeout=None):
        if not self._messages:
            raise ScriptEnded
        return self._messages.pop(0)

    async def unsubscribe(self, channel):
        self.unsubscribed.append(channel)

    async def aclose(self):
        self.closed = True


class FakeRedisClient:
    def __init__(self, pubsub_stub):
        self._pubsub = pubsub_stub

    def pubsub(self):
        return self._pubsub


class TestCardEventStreamAdapter:
    async def test_stream_yields_payloads_keepalives_then_cleans_up(self):
        pubsub = FakePubSub(
            [
                None,
                {"type": "message", "data": b'{"action":"add"}'},
                {"type": "subscribe", "data": 1},
                {"type": "message", "data": '{"action":"clear"}'},
            ]
        )
        stream = RedisCardEventStream(FakeRedisClient(pubsub))

        received = []
        with pytest.raises(ScriptEnded):
            async for message in stream.messages():
                received.append(message)

        assert received == [None, '{"action":"add"}', '{"action":"clear"}']
        assert pubsub.subscribed == [settings.CARD_CHANNEL]
        assert pubsub.unsubscribed == [settings.CARD_CHANNEL]
        assert pubsub.closed is True
