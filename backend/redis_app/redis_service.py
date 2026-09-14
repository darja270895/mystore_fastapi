import json
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any
import logging

from fastapi import FastAPI, Request
import redis.asyncio as asyncredis


@asynccontextmanager
async def create_lifespan(app: FastAPI):
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = os.getenv("REDIS_PORT", "6379")# automatically being executed when app starts up

    pool = asyncredis.ConnectionPool(  # reusable pool of connections
        host=redis_host,
        port=redis_port,
        db=0,  # default redis DB
        decode_responses=True,  # Automatically decodes Redis bytes to Python strings
        max_connections=20,
        socket_timeout=5.0,
        socket_connect_timeout=5.0
    )
    app.state.redis_pool = pool
    # pool = request.app.state.redis_pool

    # everything before yield starts before app starts receiving HTTP requests, when app is running it sits here frozen
    yield

    await pool.disconnect()  # after app shuts down


class RedisService():

    def __init__(self, client: asyncredis.Redis):
        """Raw client injection into Service layer"""

        self.redis_client = client

    async def set_value(self, key: str, value: Any, ex: int = 3600) -> str | None:
        value_json = json.dumps(value) #to json string
        return await self.redis_client.set(name=key, value=value_json, ex=ex)

    async def get_value(self, key: str) -> str | None:
        value = await self.redis_client.get(key)

        if value is None:
            return None

        return json.loads(value)

    async def delete_value(self, key: str) -> str | None:
        return await self.redis_client.delete(key)

    async def ttl_check(self, key: str):
        return await self.redis_client.ttl(key)


async def get_redis_service(request: Request) -> AsyncGenerator[RedisService | None]:
    """
        Dependency injection
        Yields Redis client instance per request
    """
    pool = request.app.state.redis_pool
    client = asyncredis.Redis(connection_pool=pool)
    try:
        await client.ping()
        yield RedisService(client)
    except asyncredis.RedisError:
        logging.info("Redis is not available")
        yield None
    finally:
        await client.close()
