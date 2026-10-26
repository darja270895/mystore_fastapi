"""PurchaseStreamConsumer unit tests: leadership checks and event handling."""

import asyncio
from unittest.mock import AsyncMock

from backend.purchases.purchase_events import PurchaseEvent
from backend.redis_app.stream_consumer import PurchaseStreamConsumer
from backend.tests.fakes import InMemoryConsumerLeadership, InMemoryPurchaseEventSource


def make_event(purchase_id: int = 1) -> PurchaseEvent:
    return PurchaseEvent(
        purchase_id=purchase_id,
        user_id=1,
        product_id=2,
        amount=1,
        product_name="Mouse",
        total_price=10.0,
    )


async def wait_for(predicate, timeout: float = 2.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not met in time")


async def test_consumer_persists_each_streamed_event():
    saved: list[PurchaseEvent] = []
    source = InMemoryPurchaseEventSource([make_event(1), make_event(2)])
    consumer = PurchaseStreamConsumer(
        source=source, leadership=InMemoryConsumerLeadership(), leader_token="token-1"
    )
    consumer._save_notification = AsyncMock(side_effect=lambda event: saved.append(event))

    async with consumer:
        await wait_for(lambda: len(saved) == 2)

    assert [event.purchase_id for event in saved] == [1, 2]
    assert consumer._task is None


async def test_consumer_advances_the_stream_cursor():
    source = InMemoryPurchaseEventSource([make_event(1), make_event(2)])
    consumer = PurchaseStreamConsumer(
        source=source, leadership=InMemoryConsumerLeadership(), leader_token="token-1"
    )
    consumer._save_notification = AsyncMock()

    async with consumer:
        await wait_for(lambda: len(source.read_calls) >= 3)

    assert source.read_calls[0] == "$"
    assert source.read_calls[1] == "1-0"
    assert source.read_calls[2] == "2-0"


async def test_consumer_refreshes_leadership_before_every_read():
    leadership = InMemoryConsumerLeadership()
    consumer = PurchaseStreamConsumer(
        source=InMemoryPurchaseEventSource([make_event()]),
        leadership=leadership,
        leader_token="token-1",
    )
    consumer._save_notification = AsyncMock()

    async with consumer:
        await wait_for(lambda: len(consumer._source.read_calls) >= 2)

    assert leadership.refresh_calls[:2] == ["token-1", "token-1"]
    assert len(leadership.refresh_calls) >= len(consumer._source.read_calls)


async def test_consumer_stops_when_leadership_is_lost():
    leadership = InMemoryConsumerLeadership(refresh_results=[False])
    consumer = PurchaseStreamConsumer(
        source=InMemoryPurchaseEventSource([make_event()]),
        leadership=leadership,
        leader_token="token-1",
    )
    consumer._save_notification = AsyncMock()

    async with consumer:
        await wait_for(lambda: consumer._task.done())
        assert consumer._source.read_calls == []
        consumer._save_notification.assert_not_awaited()


async def test_consumer_survives_a_failing_event():
    saved: list[PurchaseEvent] = []
    attempted: list[PurchaseEvent] = []

    async def flaky_save(event: PurchaseEvent) -> None:
        attempted.append(event)
        if event.purchase_id == 1:
            raise RuntimeError("db unavailable")
        saved.append(event)

    consumer = PurchaseStreamConsumer(
        source=InMemoryPurchaseEventSource([make_event(1), make_event(2)]),
        leadership=InMemoryConsumerLeadership(),
        leader_token="token-1",
    )
    consumer._save_notification = flaky_save

    async with consumer:
        await wait_for(lambda: len(saved) == 1)

    assert [event.purchase_id for event in attempted] == [1, 2]


async def test_exit_is_safe_when_listener_already_finished():
    consumer = PurchaseStreamConsumer(
        source=InMemoryPurchaseEventSource(),
        leadership=InMemoryConsumerLeadership(refresh_results=[False]),
        leader_token="token-1",
    )

    async with consumer:
        await wait_for(lambda: consumer._task.done())

    assert consumer._task is None
