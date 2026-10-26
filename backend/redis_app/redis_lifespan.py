"""
Per-worker Redis startup/shutdown.

- ConnectionPool → app.state.redis (shared by HTTP handlers)
- Separate pubsub connection → background Card event listener
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from uuid import uuid4

from fastapi import FastAPI
import redis.asyncio as asyncredis

from backend.config import settings
from backend.redis_app.adapters import build_redis_adapters
from backend.redis_app.redis_pub_sub_events import RedisPubSub
from backend.redis_app.stream_consumer import PurchaseStreamConsumer

logger = logging.getLogger(__name__)


@asynccontextmanager
async def redis_lifespan(app: FastAPI):
    """
    Per-worker startup/shutdown.
    Uses Redis connection pool for load balance.

    ! Important: migrations run once before uvicorn starts.
    """
    pool = asyncredis.ConnectionPool(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True,
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
        socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT,
    )

    redis_client = asyncredis.Redis(connection_pool=pool)
    adapters = build_redis_adapters(redis_client)

    # Pub/Sub reserves its own connection from the shared pool while listening.
    redis_pub_subscriber = redis_client.pubsub()
    await redis_pub_subscriber.subscribe(settings.CARD_CHANNEL)

    handler = RedisPubSub(
        store=adapters.card_store,
        completion=adapters.event_completion,
        channel=settings.CARD_CHANNEL,
    )

    task = asyncio.create_task(
        listen_events(redis_pub_subscriber, handler),
        name="redis-card-pubsub",
    )

    app.state.redis = redis_client
    app.state.redis_pool = pool
    app.state.redis_adapters = adapters
    app.state.pubsub_task = task
    app.state.card_pubsub_handler = handler

    logger.info("Redis ready — subscribed to %s", settings.CARD_CHANNEL)

    leader_token = uuid4().hex
    consumer: PurchaseStreamConsumer | None = None
    app.state.stream_consumer_active = False
    if await adapters.consumer_leadership.acquire(leader_token):
        consumer = PurchaseStreamConsumer(
            source=adapters.purchase_event_source,
            leadership=adapters.consumer_leadership,
            leader_token=leader_token,
        )
        await consumer.__aenter__()
        app.state.stream_consumer_active = True

    try:
        yield
    finally:
        app.state.stream_consumer_active = False
        if consumer is not None:
            await consumer.__aexit__(None, None, None)
            await adapters.consumer_leadership.release(leader_token)

        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

        with suppress(Exception):
            await redis_pub_subscriber.unsubscribe(settings.CARD_CHANNEL)
            await redis_pub_subscriber.aclose()

        await redis_client.aclose()
        await pool.disconnect()
        logger.info("Redis shutdown complete")


async def listen_events(pubsub, handler: RedisPubSub) -> None:
    """Background task: receive PUBLISH messages and apply them to Redis HASH."""
    async for message in pubsub.listen():
        if message.get("type") != "message":
            continue
        data = message.get("data")
        if data is None:
            continue
        await handler.handle_message(data)
