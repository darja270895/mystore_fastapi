"""Structural tests that protect the dependency direction and port contracts."""

import re
from pathlib import Path

from backend.card import card_ports
from backend.products import product_ports
from backend.purchases import purchase_ports
from backend.redis_app.adapters import RedisAdapters, build_redis_adapters
from backend.tests.fakes import FakeAdapters

BACKEND_ROOT = Path(__file__).resolve().parents[2]
APPLICATION_PACKAGES = ("products", "purchases", "card", "users")
INFRASTRUCTURE_IMPORT = re.compile(r"^\s*(?:from|import)\s+\S*redis", re.MULTILINE)


def test_application_packages_never_import_infrastructure():
    offenders = [
        module.relative_to(BACKEND_ROOT).as_posix()
        for package in APPLICATION_PACKAGES
        for module in (BACKEND_ROOT / package).rglob("*.py")
        if INFRASTRUCTURE_IMPORT.search(module.read_text(encoding="utf-8"))
    ]

    assert offenders == []


def test_every_redis_adapter_shares_one_client():
    class Sentinel:
        """Stands in for the pooled client; identity is what we assert on."""

    client = Sentinel()
    adapters = build_redis_adapters(client)  # type: ignore[arg-type]

    command_layers = [
        adapters.product_cache._cache,
        adapters.purchase_coordinator._rates,
        adapters.purchase_coordinator._locks,
        adapters.purchase_events._streams,
        adapters.purchase_events._publisher,
        adapters.purchase_events._zsets,
        adapters.recent_purchases._zsets,
        adapters.card_store._hashes,
        adapters.card_store._cache,
        adapters.card_publisher._publisher,
        adapters.event_completion._cache,
        adapters.purchase_event_source._streams,
        adapters.consumer_leadership._locks,
    ]

    assert all(layer.redis_client is client for layer in command_layers)
    assert adapters.card_event_stream._client is client


def test_fake_adapters_cover_the_whole_production_bundle():
    assert set(RedisAdapters.__dataclass_fields__) <= set(FakeAdapters.__dataclass_fields__)


def test_fakes_satisfy_the_declared_ports():
    adapters = FakeAdapters()
    protocol_bindings = [
        (product_ports.ProductCache, adapters.product_cache),
        (purchase_ports.PurchaseCoordinator, adapters.purchase_coordinator),
        (purchase_ports.PurchaseEvents, adapters.purchase_events),
        (purchase_ports.RecentPurchaseFeed, adapters.recent_purchases),
        (purchase_ports.PurchaseEventSource, adapters.purchase_event_source),
        (purchase_ports.ConsumerLeadership, adapters.consumer_leadership),
        (card_ports.CardStore, adapters.card_store),
        (card_ports.CardEventPublisher, adapters.card_publisher),
        (card_ports.EventCompletion, adapters.event_completion),
        (card_ports.CardEventStream, adapters.card_event_stream),
    ]

    for port, implementation in protocol_bindings:
        missing = [
            name
            for name in port.__protocol_attrs__
            if not callable(getattr(implementation, name, None))
        ]
        assert missing == [], f"{type(implementation).__name__} is missing {missing}"
