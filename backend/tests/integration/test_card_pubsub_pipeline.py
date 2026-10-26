"""Card publish → subscribe → apply pipeline over a real Redis connection."""

import asyncio
from contextlib import suppress

import pytest

from backend.card.card_events import CardEvent
from backend.config import settings
from backend.redis_app.redis_lifespan import listen_events
from backend.redis_app.redis_pub_sub_events import RedisPubSub


@pytest.fixture
async def card_listener(redis_client, redis_adapters):
    """Mirror the lifespan wiring: one dedicated subscriber connection."""
    handler = RedisPubSub(
        store=redis_adapters.card_store,
        completion=redis_adapters.event_completion,
        channel=settings.CARD_CHANNEL,
    )
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(settings.CARD_CHANNEL)
    task = asyncio.create_task(listen_events(pubsub, handler))

    yield handler

    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    await pubsub.unsubscribe(settings.CARD_CHANNEL)
    await pubsub.aclose()


async def publish_and_wait(adapters, event: CardEvent) -> None:
    await adapters.card_publisher.publish(event)
    await adapters.event_completion.wait_applied(event.event_id, timeout_s=3)


async def test_published_card_events_are_applied_by_the_subscriber(
    redis_adapters, card_listener
):
    await publish_and_wait(
        redis_adapters,
        CardEvent(action="add", user_id=1, product_id=7, amount=2, product_name="Book"),
    )

    card = await redis_adapters.card_store.get(1)
    assert card.total_items == 2
    assert card.items[0].product_name == "Book"

    await publish_and_wait(
        redis_adapters, CardEvent(action="remove", user_id=1, product_id=7)
    )

    assert (await redis_adapters.card_store.get(1)).total_items == 0


async def test_a_replayed_event_is_applied_only_once(redis_adapters, card_listener):
    event = CardEvent(action="add", user_id=2, product_id=9, amount=1)

    await publish_and_wait(redis_adapters, event)
    await redis_adapters.card_publisher.publish(event)
    await asyncio.sleep(0.2)

    assert (await redis_adapters.card_store.get(2)).total_items == 1


async def test_clear_event_empties_the_card_hash(redis_adapters, card_listener):
    await publish_and_wait(
        redis_adapters, CardEvent(action="add", user_id=3, product_id=9, amount=4)
    )

    await publish_and_wait(redis_adapters, CardEvent(action="clear", user_id=3))

    assert (await redis_adapters.card_store.get(3)).items == []


async def test_malformed_payloads_do_not_kill_the_listener(
    redis_client, redis_adapters, card_listener
):
    await redis_client.publish(settings.CARD_CHANNEL, "not-json")
    await asyncio.sleep(0.1)

    await publish_and_wait(
        redis_adapters, CardEvent(action="add", user_id=4, product_id=1, amount=1)
    )

    assert (await redis_adapters.card_store.get(4)).total_items == 1
