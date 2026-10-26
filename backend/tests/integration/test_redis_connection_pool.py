"""The whole app shares one pool: many concurrent commands, bounded connections."""

import asyncio

from backend.redis_app.adapters import build_redis_adapters
from backend.redis_app.redis_service import RedisCacheService


async def test_many_concurrent_commands_share_one_pool(redis_client):
    cache = RedisCacheService(redis_client)

    async def round_trip(number: int):
        await cache.set_value(f"it:pool:{number}", {"n": number}, ex=10)
        return await cache.get_value(f"it:pool:{number}")

    results = await asyncio.gather(*(round_trip(index) for index in range(50)))

    assert results == [{"n": index} for index in range(50)]
    pool = redis_client.connection_pool
    assert len(pool._in_use_connections) == 0
    assert len(pool._available_connections) <= 50


async def test_mixed_workloads_run_concurrently_on_the_same_client(redis_client):
    adapters = build_redis_adapters(redis_client)

    cache_write, rate_limit, lock = await asyncio.gather(
        adapters.product_cache.ttl(1),
        adapters.purchase_coordinator.check_rate_limit(1),
        adapters.purchase_coordinator.acquire_stock_lock(1, "token"),
    )

    assert cache_write == -2
    assert rate_limit == (True, 1)
    assert lock is True
