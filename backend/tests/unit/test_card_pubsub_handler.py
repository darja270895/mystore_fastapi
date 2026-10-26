"""RedisPubSub subscriber unit tests: claim-once semantics and action routing."""

from unittest.mock import AsyncMock

import pytest

from backend.card.card_events import CardEvent
from backend.redis_app.redis_pub_sub_events import RedisPubSub
from backend.tests.fakes import InMemoryCardStore, InMemoryEventCompletion


@pytest.fixture
def store() -> InMemoryCardStore:
    return InMemoryCardStore()


@pytest.fixture
def completion() -> InMemoryEventCompletion:
    return InMemoryEventCompletion()


@pytest.fixture
def handler(store, completion) -> RedisPubSub:
    return RedisPubSub(store=store, completion=completion, channel="channel:card")


async def test_add_event_updates_store_and_marks_applied(handler, store, completion):
    event = CardEvent(action="add", user_id=1, product_id=2, amount=3, product_name="Mouse")

    await handler.handle_message(event.model_dump_json())

    assert store.amounts[1][2] == 3
    assert store.names[1][2] == "Mouse"
    assert event.event_id in completion.applied


async def test_add_event_accepts_bytes_payload(handler, store):
    event = CardEvent(action="add", user_id=1, product_id=2, amount=1)

    await handler.handle_message(event.model_dump_json().encode())

    assert store.amounts[1][2] == 1


async def test_remove_event_deletes_single_product(handler, store):
    await handler.handle_message(
        CardEvent(action="add", user_id=1, product_id=2, amount=2).model_dump_json()
    )
    await handler.handle_message(
        CardEvent(action="remove", user_id=1, product_id=2).model_dump_json()
    )

    assert store.amounts[1] == {}


async def test_clear_event_empties_card(handler, store):
    await handler.handle_message(
        CardEvent(action="add", user_id=1, product_id=2, amount=2).model_dump_json()
    )
    await handler.handle_message(CardEvent(action="clear", user_id=1).model_dump_json())

    assert 1 not in store.amounts


async def test_invalid_payload_is_ignored(handler, completion):
    await handler.handle_message("not-json")

    assert completion.claimed == set()
    assert completion.applied == set()


async def test_duplicate_event_is_applied_once(handler, store, completion):
    event = CardEvent(action="add", user_id=1, product_id=2, amount=1)

    await handler.handle_message(event.model_dump_json())
    await handler.handle_message(event.model_dump_json())

    assert store.amounts[1][2] == 1
    assert len(completion.claimed) == 1


async def test_event_with_unsupported_action_is_rejected(handler, store, completion):
    import json

    payload = CardEvent(action="add", user_id=1, product_id=2).model_dump()
    payload["action"] = "explode"

    await handler.handle_message(json.dumps(payload, default=str))

    assert store.amounts == {}
    assert completion.applied == set()


async def test_store_failure_releases_claim_for_retry(completion):
    failing_store = AsyncMock()
    failing_store.apply_add.side_effect = RuntimeError("redis down")
    handler = RedisPubSub(store=failing_store, completion=completion, channel="channel:card")
    event = CardEvent(action="add", user_id=1, product_id=2, amount=1)

    await handler.handle_message(event.model_dump_json())

    assert completion.applied == set()
    assert event.event_id not in completion.claimed


async def test_add_without_product_id_is_skipped(handler, store, completion):
    event = CardEvent(action="add", user_id=1, product_id=None, amount=1)

    await handler.handle_message(event.model_dump_json())

    assert store.amounts == {}
    assert event.event_id in completion.applied
