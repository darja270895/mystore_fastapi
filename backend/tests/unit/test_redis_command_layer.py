"""Command-layer unit tests: the thin wrappers around raw Redis commands."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from backend.config import settings
from backend.redis_app.redis_service import (
    RedisCacheService,
    RedisHashService,
    RedisLockService,
    RedisPublishService,
    RedisRateLimiter,
    RedisStreamService,
    RedisZSetService,
)


class TestCacheService:
    async def test_set_value_serialises_json_and_applies_default_ttl(self):
        client = AsyncMock()
        client.set.return_value = True

        assert await RedisCacheService(client).set_value("k", {"a": 1}) is True

        client.set.assert_awaited_once_with(
            name="k", value=json.dumps({"a": 1}), ex=settings.CACHE_TTL_SECONDS
        )

    async def test_set_value_honours_explicit_ttl(self):
        client = AsyncMock()

        await RedisCacheService(client).set_value("k", [1, 2], ex=5)

        assert client.set.await_args.kwargs["ex"] == 5

    async def test_set_nx_is_only_true_for_a_fresh_key(self):
        client = AsyncMock()
        service = RedisCacheService(client)

        client.set.return_value = True
        assert await service.set_nx("k", "1", ex=30) is True

        client.set.return_value = None
        assert await service.set_nx("k", "1", ex=30) is False

    async def test_get_value_deserialises_or_returns_none(self):
        client = AsyncMock()
        service = RedisCacheService(client)

        client.get.return_value = '{"a": 1}'
        assert await service.get_value("k") == {"a": 1}

        client.get.return_value = None
        assert await service.get_value("k") is None

    async def test_delete_exists_and_ttl_coerce_redis_replies(self):
        client = AsyncMock()
        client.delete.return_value = 1
        client.exists.return_value = 0
        client.ttl.return_value = 7
        service = RedisCacheService(client)

        assert await service.delete_value("k") == 1
        assert await service.exists("k") is False
        assert await service.ttl_check("k") == 7

    async def test_concurrent_writes_share_the_single_client(self):
        client = AsyncMock()

        async def slow_set(*args, **kwargs):
            await asyncio.sleep(0.01)
            return True

        client.set.side_effect = slow_set
        service = RedisCacheService(client)

        results = await asyncio.gather(
            *(service.set_value(f"key_{index}", index) for index in range(20))
        )

        assert results == [True] * 20
        assert client.set.await_count == 20


class TestLockService:
    async def test_acquire_uses_set_nx_px(self):
        client = AsyncMock()
        client.set.return_value = True

        assert await RedisLockService(client).acquire_lock("lock", "token", 500) is True

        client.set.assert_awaited_once_with(name="lock", value="token", nx=True, px=500)

    async def test_acquire_falls_back_to_configured_ttl(self):
        client = AsyncMock()
        client.set.return_value = True

        await RedisLockService(client).acquire_lock("lock", "token")

        assert client.set.await_args.kwargs["px"] == settings.STOCK_LOCK_TTL_MS

    async def test_acquire_returns_false_when_already_held(self):
        client = AsyncMock()
        client.set.return_value = None

        assert await RedisLockService(client).acquire_lock("lock", "token") is False

    async def test_refresh_and_release_run_owner_checked_lua(self):
        client = AsyncMock()
        client.eval.return_value = 1
        service = RedisLockService(client)

        assert await service.refresh_lock("lock", "token", 800) is True
        assert await service.release_lock("lock", "token") is True

        refresh_args = client.eval.await_args_list[0].args
        assert refresh_args[1:] == (1, "lock", "token", 800)
        assert 'redis.call("pexpire"' in refresh_args[0]

        release_args = client.eval.await_args_list[1].args
        assert release_args[1:] == (1, "lock", "token")
        assert 'redis.call("del"' in release_args[0]

    async def test_release_is_false_when_token_does_not_match(self):
        client = AsyncMock()
        client.eval.return_value = 0

        assert await RedisLockService(client).release_lock("lock", "other") is False


class TestRateLimiter:
    def _client_with_count(self, count: int):
        client = MagicMock()
        pipeline = MagicMock()
        pipeline.execute = AsyncMock(return_value=[count, True])
        client.pipeline.return_value = pipeline
        return client, pipeline

    async def test_counts_within_limit_are_allowed(self):
        client, pipeline = self._client_with_count(3)

        assert await RedisRateLimiter(client).check_rate_limit("rl", limit=5) == (True, 3)

        pipeline.incr.assert_called_once_with("rl")
        pipeline.expire.assert_called_once_with("rl", 60, nx=True)

    async def test_counts_above_limit_are_rejected(self):
        client, _ = self._client_with_count(6)

        allowed, count = await RedisRateLimiter(client).check_rate_limit(
            "rl", limit=5, window_seconds=30
        )

        assert (allowed, count) == (False, 6)


class TestStreamService:
    async def test_stream_add_returns_message_id_as_string(self):
        client = AsyncMock()
        client.xadd.return_value = "1-0"

        assert await RedisStreamService(client).stream_add("s", {"a": "1"}) == "1-0"

        client.xadd.assert_awaited_once_with("s", {"a": "1"})

    async def test_stream_read_passes_blocking_options(self):
        client = AsyncMock()
        client.xread.return_value = [("s", [("1-0", {"a": "1"})])]

        result = await RedisStreamService(client).stream_read("s", "$", count=5, block_ms=10)

        assert result == [("s", [("1-0", {"a": "1"})])]
        client.xread.assert_awaited_once_with(streams={"s": "$"}, count=5, block=10)

    async def test_stream_read_normalises_none_to_empty_list(self):
        client = AsyncMock()
        client.xread.return_value = None

        assert await RedisStreamService(client).stream_read("s", "$") == []


class TestPublishService:
    async def test_dict_payloads_are_json_encoded(self):
        client = AsyncMock()
        client.publish.return_value = 2

        assert await RedisPublishService(client).publish("ch", {"a": 1}) == 2

        client.publish.assert_awaited_once_with("ch", json.dumps({"a": 1}))

    async def test_string_payloads_are_sent_untouched(self):
        client = AsyncMock()
        client.publish.return_value = 0

        await RedisPublishService(client).publish("ch", "raw")

        client.publish.assert_awaited_once_with("ch", "raw")


class TestZSetService:
    async def test_zadd_scored_and_zrevrange(self):
        client = AsyncMock()
        client.zadd.return_value = 1
        client.zrevrange.return_value = ["b", "a"]
        service = RedisZSetService(client)

        assert await service.zadd_scored("z", "b", 2.0) == 1
        assert await service.zrevrange("z", 0, 1) == ["b", "a"]

        client.zadd.assert_awaited_once_with("z", {"b": 2.0})

    async def test_trim_removes_only_the_overflow(self):
        client = AsyncMock()
        client.zcard.return_value = 12

        await RedisZSetService(client).zcard_trim("z", 10)

        client.zremrangebyrank.assert_awaited_once_with("z", 0, 1)

    async def test_trim_is_a_no_op_below_the_cap(self):
        client = AsyncMock()
        client.zcard.return_value = 5

        await RedisZSetService(client).zcard_trim("z", 10)

        client.zremrangebyrank.assert_not_awaited()


class TestHashService:
    async def test_hash_commands_coerce_replies(self):
        client = AsyncMock()
        client.hincrby.return_value = 4
        client.hgetall.return_value = {"1": "2"}
        client.hdel.return_value = 1
        client.hset.return_value = 1
        service = RedisHashService(client)

        assert await service.hincrby("h", "1", 2) == 4
        assert await service.hgetall("h") == {"1": "2"}
        assert await service.hdel("h", "1", "2") == 1
        assert await service.hset("h", "1", "Book") == 1

        client.hdel.assert_awaited_once_with("h", "1", "2")

    async def test_hdel_without_fields_skips_the_round_trip(self):
        client = AsyncMock()

        assert await RedisHashService(client).hdel("h") == 0
        client.hdel.assert_not_awaited()
