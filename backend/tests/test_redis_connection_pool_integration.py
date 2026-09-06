import asyncio
from typing import Coroutine

import pytest

from unittest.mock import AsyncMock

from redis_app.redis_service import RedisService
import redis.asyncio as asyncredis



async def redis_operation(client, number):

    async with client.client() as connection:

        print(
            f"Task {number}: acquired connection"
        )

        await asyncio.sleep(2)

        await connection.set(
            f"test:{number}",
            str(number)
        )

        print(
            f"Task {number}: finished"
        )


@pytest.mark.asyncio
async def test_redis_concurrency():
    pool = asyncredis.ConnectionPool(
        host="localhost",
        port=6379,
        db=0,
        decode_responses=True,
        max_connections=20,
        socket_timeout=5.0,
        socket_connect_timeout=5.0
    )

    redis_client = asyncredis.Redis(connection_pool=pool)

    tasks = [
        redis_operation(redis_client, i)
        for i in range(25)
    ]
    await asyncio.gather(*tasks) #конкурентный запуск

    # async def operation(i):
    #     await redis_client.set(f"test:{i}", str(i))
    #     return await redis_client.get(f"test:{i}")
    #
    # results = await asyncio.gather(*(operation(i) for i in range(20)))
    #
    # assert results == [str(i) for i in range(20)]

    await redis_client.aclose()
    await pool.disconnect()