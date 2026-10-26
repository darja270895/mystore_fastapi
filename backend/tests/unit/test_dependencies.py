"""Composition root unit tests: providers wire ports, never Redis internals."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from backend.dependencies import (
    get_card_event_stream,
    get_card_service,
    get_product_service,
    get_purchase_service,
    get_redis_adapters,
)
from backend.tests.fakes import FakeAdapters


def make_request(adapters=None):
    state = SimpleNamespace()
    if adapters is not None:
        state.redis_adapters = adapters
    return SimpleNamespace(app=SimpleNamespace(state=state))


def test_get_redis_adapters_returns_none_when_redis_is_disabled():
    assert get_redis_adapters(make_request()) is None


def test_get_redis_adapters_returns_app_state_bundle():
    adapters = FakeAdapters()

    assert get_redis_adapters(make_request(adapters)) is adapters


def test_providers_inject_matching_ports():
    adapters = FakeAdapters()
    db = AsyncMock()

    product_service = get_product_service(db=db, adapters=adapters)
    purchase_service = get_purchase_service(db=db, adapters=adapters)
    card_service = get_card_service(db=db, adapters=adapters)

    assert product_service.cache is adapters.product_cache
    assert purchase_service.coordinator is adapters.purchase_coordinator
    assert purchase_service.events is adapters.purchase_events
    assert purchase_service.recent_feed is adapters.recent_purchases
    assert card_service.store is adapters.card_store
    assert card_service.publisher is adapters.card_publisher
    assert card_service.completion is adapters.event_completion
    assert get_card_event_stream(adapters=adapters) is adapters.card_event_stream


def test_card_service_receives_a_purchase_creator_port():
    card_service = get_card_service(db=AsyncMock(), adapters=FakeAdapters())

    assert hasattr(card_service.purchase_creator, "create_purchase")


def test_providers_degrade_to_none_ports_without_redis():
    db = AsyncMock()

    assert get_product_service(db=db, adapters=None).cache is None
    purchase_service = get_purchase_service(db=db, adapters=None)
    assert (purchase_service.coordinator, purchase_service.events) == (None, None)
    card_service = get_card_service(db=db, adapters=None)
    assert (card_service.store, card_service.publisher, card_service.completion) == (
        None,
        None,
        None,
    )
    assert get_card_event_stream(adapters=None) is None
