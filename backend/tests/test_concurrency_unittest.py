import asyncio
import pytest

from unittest.mock import AsyncMock

from redis_app.redis_service import RedisService


@pytest.mark.asyncio
async def test_set_value():
    redis_client = AsyncMock()
    redis_service = RedisService(redis_client)

    async def fake_set(*args, **kwargs):
        await asyncio.sleep(0.1)
        return "OK"

    redis_client.set.side_effect = fake_set

    tasks = [
        redis_service.set_value(f"key_{i}", f"value_{i}") for i in range(20)
    ]

    result = await asyncio.gather(*tasks)

    assert result == ["OK"] * 20
    assert redis_client.await_count == 20