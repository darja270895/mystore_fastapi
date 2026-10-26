"""
Redis infrastructure layer (redis.asyncio).

Lifespan is safe for multi-worker uvicorn:
- each worker gets its own Redis pool
- only ONE worker becomes stream-consumer leader (Redis lock)
- schema is NOT created here — run Alembic before starting uvicorn
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Callable, AsyncIterator

import redis.asyncio as asyncredis
from redis.asyncio.client import Pipeline

from backend.config import settings

# Atomic operations - redis Distributed locking
_RELEASE_LOCK_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

_REFRESH_LOCK_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("pexpire", KEYS[1], ARGV[2])
else
    return 0
end
"""

_IMPLEMENT_FIXED_WINDOW_LUA = """
local count = redis.call("INCR", KEYS[1])
if count == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end
return count
"""


class BaseRedis:
    def __init__(self, client: asyncredis.Redis):
        self.redis_client = client


class RedisCacheService(BaseRedis):
    """Redis cache service, only cache operations enabled"""

    # Cache functionality
    async def set_value(self, key: str, value, ex: int | None = None) -> bool:
        ttl = settings.CACHE_TTL_SECONDS if ex is None else ex
        return bool(await self.redis_client.set(name=key, value=json.dumps(value), ex=ttl))

    async def set_nx(self, key: str, value: str, ex: int = 60) -> bool:
        """Set if not exist"""
        result = await self.redis_client.set(name=key, value=value, nx=True, ex=ex)
        return result is True

    async def get_value(self, key: str) -> Any | None:
        value = await self.redis_client.get(key)
        if value is None:
            return None
        return json.loads(value)

    async def delete_value(self, key: str) -> int:
        return int(await self.redis_client.delete(key))

    async def exists(self, key: str) -> bool:
        return bool(await self.redis_client.exists(key))

    async def ttl_check(self, key: str) -> int:
        return int(await self.redis_client.ttl(key))


class RedisLockService(BaseRedis):
    """Redis distributed lock service, aquires lock on resource. 
    Currently used for stock lock when bying products from Card    """

    async def acquire_lock(self, key: str, token: str, ttl_ms: int | None = None) -> bool:
        ttl = settings.STOCK_LOCK_TTL_MS if ttl_ms is None else ttl_ms
        result = await self.redis_client.set(name=key, value=token, nx=True, px=ttl)
        return result is True

    async def refresh_lock(self, key: str, token: str, ttl_ms: int | None = None) -> bool:
        """Extend lock TTL only if we still own the token (XX + value check via Lua GET)."""

        ttl = settings.STOCK_LOCK_TTL_MS if ttl_ms is None else ttl_ms
        # Thread-save operation
        result = await self.redis_client.eval(
            _REFRESH_LOCK_LUA,
            1,
            key,
            token,
            ttl,
        )

        return bool(result)

    async def release_lock(self, key: str, token: str) -> bool:
        released = await self.redis_client.eval(_RELEASE_LOCK_LUA, 1, key, token)
        return bool(released)


class RedisRateLimiter(BaseRedis):
    """fixed window counter in Redis (shared across workers).
    Main goal is to limit parallel requests to DB so there wouldn't be a Db overloading.
    """

    async def check_rate_limit(
            self,
            key: str,
            limit: int,
            window_seconds: int = 60,
    ) -> tuple[bool, int]:

        # registering Script - returns callable Script object
        script = self.redis_client.register_script(_IMPLEMENT_FIXED_WINDOW_LUA)
        count = int(await script(keys=[key], args=[window_seconds]))
        return count <= limit, count


class RedisStreamService(BaseRedis):
    """Notifications (producer-consumer)"""

    async def stream_add(self, stream: str, fields: dict[str, str]) -> str:
        return str(await self.redis_client.xadd(stream, fields))

    async def stream_read(
            self,
            stream: str,
            last_id: str,
            count: int = 10,
            block_ms: int = 2_000,
    ) -> list[tuple[str, list[tuple[str, dict[str, str]]]]]:
        result = await self.redis_client.xread(
            streams={stream: last_id},
            count=count,
            block=block_ms,
        )
        return result or []


class RedisPublishService(BaseRedis):
    """for UI live updates (SSE) and for Card event fan-out. Not durable (unlike Streams)."""

    async def publish(self, channel: str, payload: str | dict[str, Any]) -> int:
        message = payload if isinstance(payload, str) else json.dumps(payload)
        return int(await self.redis_client.publish(channel, message))


class RedisZSetService(BaseRedis):
    """Recent activity - recent purchases feed. Sorted sets."""

    async def zadd_scored(self, key: str, member: str, score: float) -> int:
        return int(await self.redis_client.zadd(key, {member: score}))

    async def zrevrange(self, key: str, start: int = 0, end: int = 49) -> list[str]:
        return list(await self.redis_client.zrevrange(key, start, end))

    async def zcard_trim(self, key: str, max_size: int) -> None:
        size = await self.redis_client.zcard(key)
        if size > max_size:
            await self.redis_client.zremrangebyrank(key, 0, size - max_size - 1)


class RedisHashService(BaseRedis):
    """Storing card state in Redis"""

    async def hincrby(self, key: str, field: str, amount: int) -> int:
        """Card events, increment by some number"""
        return int(await self.redis_client.hincrby(key, field, amount))

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(await self.redis_client.hgetall(key))

    async def hdel(self, key: str, *fields: str) -> int:
        if not fields:
            return 0
        return int(await self.redis_client.hdel(key, *fields))

    async def hset(self, key: str, field: str, value: str) -> int:
        """Card events, overwriting the valuy by key"""
        return int(await self.redis_client.hset(key, field, value))


class RedisPipelineService(BaseRedis):

    @asynccontextmanager
    async def pipeline(self, transaction: bool=True) -> AsyncIterator[Pipeline]:
        """ Manages pipeline Resource's lifecycle and resets its state in exit"""
        async with self.redis_client.pipeline(transaction=transaction) as pipe:
            try:
                yield pipe
            except Exception:
                logging.exception("Error building Redis pipeline")
                raise


    async def set_pack(self, data: dict) -> bool:
        async with self.pipeline(transaction=False) as pipeline:
            for key, value in data.items():
                # buffering commands
                pipeline.set(name=f"seat: {key}", value=value) #queue command
            results = await pipeline.execute()
            return all(results)

    async def get_chain(self, keys) -> dict[str, Any]:

        async with self.pipeline(transaction=False) as pipeline:
            for key in keys:
                pipeline.get(key) #queue command
            values = await pipeline.execute()
            return dict(zip(keys, values))

    async def universal_pipeline_execute(self, commands: list[tuple], transaction=True):
        """
        Usage example:
        universal_pipeline([("set", "a", 1), ("get", "b"), ("incr", "c")])
        :param transaction: True or False (depends on whether we want MULTI\EXEC (set to True) or not)
        :param commands: list of commands

        """
        async with self.pipeline(transaction=transaction) as pipeline:
            for name, *args in commands:
                getattr(pipeline, name)(*args)
            return await pipeline.execute()

    # async def execute(
    #         self,
    #         queue: Callable[[Pipeline], None],
    #         *,
    #         transaction: bool = True,
    # ) -> list[Any]:
    #     """Run the commands queued by `queue` in a single round trip.
    #     The caller owns keys/payloads; this method owns the connection
    #     lifecycle. transaction=True wraps the batch in MULTI/EXEC (atomic),
    #     transaction=False only batches the network I/O.
    #     Results come back in queue order; the first failing command raises.
    #     """
    #     async with self.redis_client.pipeline(transaction=transaction) as pipe:
    #         queue(pipe)  # buffering only - nothing is sent yet
    #         return await pipe.execute()


