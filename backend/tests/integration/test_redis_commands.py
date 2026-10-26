"""Integration tests for the Redis command layer against a real server.

Skipped automatically when no Redis is reachable (see the ``redis_client``
fixture).
"""

import asyncio

from backend.redis_app.redis_service import (
    RedisCacheService,
    RedisHashService,
    RedisLockService,
    RedisPublishService,
    RedisRateLimiter,
    RedisStreamService,
    RedisZSetService,
)


class TestCacheCommands:
    async def test_round_trip_with_ttl(self, redis_client):
        cache = RedisCacheService(redis_client)

        assert await cache.set_value("it:product:1", {"id": 1}, ex=30) is True
        assert await cache.get_value("it:product:1") == {"id": 1}
        assert await cache.exists("it:product:1") is True
        assert 0 < await cache.ttl_check("it:product:1") <= 30

        assert await cache.delete_value("it:product:1") == 1
        assert await cache.get_value("it:product:1") is None
        assert await cache.exists("it:product:1") is False

    async def test_ttl_check_reports_missing_and_persistent_keys(self, redis_client):
        cache = RedisCacheService(redis_client)
        await redis_client.set("it:persistent", "1")

        assert await cache.ttl_check("it:missing") == -2
        assert await cache.ttl_check("it:persistent") == -1

    async def test_set_nx_only_wins_once(self, redis_client):
        cache = RedisCacheService(redis_client)

        assert await cache.set_nx("it:marker", "1", ex=30) is True
        assert await cache.set_nx("it:marker", "1", ex=30) is False

    async def test_value_expires_after_its_ttl(self, redis_client):
        cache = RedisCacheService(redis_client)
        await cache.set_value("it:short", {"a": 1}, ex=1)

        await redis_client.pexpire("it:short", 20)
        await asyncio.sleep(0.1)

        assert await cache.get_value("it:short") is None


class TestLockCommands:
    async def test_lock_is_exclusive_and_token_bound(self, redis_client):
        locks = RedisLockService(redis_client)

        assert await locks.acquire_lock("it:lock", "token-a", ttl_ms=5_000) is True
        assert await locks.acquire_lock("it:lock", "token-b", ttl_ms=5_000) is False

        assert await locks.release_lock("it:lock", "token-b") is False
        assert await locks.release_lock("it:lock", "token-a") is True
        assert await locks.acquire_lock("it:lock", "token-b", ttl_ms=5_000) is True

    async def test_refresh_extends_only_for_the_owner(self, redis_client):
        locks = RedisLockService(redis_client)
        await locks.acquire_lock("it:lock", "token-a", ttl_ms=500)

        assert await locks.refresh_lock("it:lock", "token-b", ttl_ms=5_000) is False
        assert await locks.refresh_lock("it:lock", "token-a", ttl_ms=5_000) is True
        assert await redis_client.pttl("it:lock") > 1_000

    async def test_lock_disappears_when_its_ttl_elapses(self, redis_client):
        locks = RedisLockService(redis_client)
        await locks.acquire_lock("it:lock", "token-a", ttl_ms=50)

        await asyncio.sleep(0.15)

        assert await locks.acquire_lock("it:lock", "token-b", ttl_ms=5_000) is True


class TestRateLimiterCommands:
    async def test_counter_increments_and_window_expires(self, redis_client):
        limiter = RedisRateLimiter(redis_client)

        results = [
            await limiter.check_rate_limit("it:rl", limit=2, window_seconds=60)
            for _ in range(3)
        ]

        assert results == [(True, 1), (True, 2), (False, 3)]
        assert 0 < await redis_client.ttl("it:rl") <= 60

    async def test_window_ttl_is_set_once_per_window(self, redis_client):
        limiter = RedisRateLimiter(redis_client)
        await limiter.check_rate_limit("it:rl", limit=10, window_seconds=60)
        await redis_client.expire("it:rl", 5)

        await limiter.check_rate_limit("it:rl", limit=10, window_seconds=60)

        assert await redis_client.ttl("it:rl") <= 5


class TestStreamCommands:
    async def test_messages_are_appended_and_read_back_in_order(self, redis_client):
        streams = RedisStreamService(redis_client)

        first = await streams.stream_add("it:stream", {"purchase_id": "1"})
        second = await streams.stream_add("it:stream", {"purchase_id": "2"})

        batches = await streams.stream_read("it:stream", last_id="0", block_ms=50)
        entries = [entry for _stream, entries in batches for entry in entries]

        assert [message_id for message_id, _ in entries] == [first, second]
        assert entries[0][1] == {"purchase_id": "1"}

    async def test_reading_from_the_tail_returns_nothing_when_idle(self, redis_client):
        streams = RedisStreamService(redis_client)
        await streams.stream_add("it:stream", {"purchase_id": "1"})

        assert await streams.stream_read("it:stream", last_id="$", block_ms=50) == []


class TestPublishCommands:
    async def test_subscriber_receives_the_published_payload(self, redis_client):
        publisher = RedisPublishService(redis_client)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("it:channel")
        await read_until_message(pubsub, expect_message=False)

        assert await publisher.publish("it:channel", {"event": "added"}) == 1

        message = await read_until_message(pubsub)
        assert message["data"] == '{"event": "added"}'

        await pubsub.unsubscribe("it:channel")
        await pubsub.aclose()

    async def test_publishing_without_subscribers_reaches_nobody(self, redis_client):
        assert await RedisPublishService(redis_client).publish("it:empty", "ping") == 0


class TestZSetCommands:
    async def test_members_come_back_newest_first_and_are_trimmed(self, redis_client):
        zsets = RedisZSetService(redis_client)
        for index in range(5):
            await zsets.zadd_scored("it:zset", member=f"event-{index}", score=float(index))

        assert await zsets.zrevrange("it:zset", 0, 1) == ["event-4", "event-3"]

        await zsets.zcard_trim("it:zset", max_size=2)

        assert await redis_client.zcard("it:zset") == 2
        assert await zsets.zrevrange("it:zset", 0, 9) == ["event-4", "event-3"]


class TestHashCommands:
    async def test_card_hash_lifecycle(self, redis_client):
        hashes = RedisHashService(redis_client)

        assert await hashes.hincrby("it:card", "7", 2) == 2
        assert await hashes.hincrby("it:card", "7", 3) == 5
        await hashes.hset("it:card:names", "7", "Book")

        assert await hashes.hgetall("it:card") == {"7": "5"}
        assert await hashes.hgetall("it:card:names") == {"7": "Book"}

        assert await hashes.hdel("it:card", "7") == 1
        assert await hashes.hgetall("it:card") == {}


async def read_until_message(pubsub, expect_message: bool = True, timeout: float = 2.0):
    """Drain subscribe confirmations and return the next real message."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
        if message is not None:
            return message
        if not expect_message:
            return None
    raise AssertionError("no message received from Redis Pub/Sub")
