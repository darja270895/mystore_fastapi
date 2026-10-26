"""In-memory implementations of the application ports.

These let unit and end-to-end tests exercise the real services, routers and
Pub/Sub handler without talking to Redis.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from backend.card.card_events import CardEvent
from backend.card.card_schemas import CardItem, CardResponse
from backend.products.product_schemas import ProductResponse
from backend.purchases.purchase_events import PurchaseEvent
from backend.redis_app.redis_pub_sub_events import RedisPubSub

CARD_CHANNEL = "channel:card"


class InMemoryProductCache:
    def __init__(self, ttl: int = 3600):
        self.values: dict[int, ProductResponse] = {}
        self.ttl_seconds = ttl
        self.put_calls: list[int] = []
        self.invalidated: list[int] = []

    async def get(self, product_id: int) -> ProductResponse | None:
        return self.values.get(product_id)

    async def put(self, product_id: int, product: ProductResponse) -> None:
        self.values[product_id] = product
        self.put_calls.append(product_id)

    async def invalidate(self, product_id: int) -> None:
        self.values.pop(product_id, None)
        self.invalidated.append(product_id)

    async def ttl(self, product_id: int) -> int:
        return self.ttl_seconds if product_id in self.values else -2


class InMemoryPurchaseCoordinator:
    """Rate limiter + stock lock with the same semantics as the Redis adapter."""

    def __init__(self, limit: int = 10, lock_available: bool = True):
        self.limit = limit
        self.lock_available = lock_available
        self.counters: dict[int, int] = {}
        self.locks: dict[int, str] = {}
        self.released: list[tuple[int, str]] = []

    async def check_rate_limit(self, user_id: int) -> tuple[bool, int]:
        count = self.counters.get(user_id, 0) + 1
        self.counters[user_id] = count
        return count <= self.limit, count

    async def acquire_stock_lock(self, product_id: int, token: str) -> bool:
        if not self.lock_available or product_id in self.locks:
            return False
        self.locks[product_id] = token
        return True

    async def release_stock_lock(self, product_id: int, token: str) -> None:
        if self.locks.get(product_id) == token:
            del self.locks[product_id]
        self.released.append((product_id, token))


class InMemoryRecentPurchaseFeed:
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.members: list[dict] = []

    def record(self, event: PurchaseEvent) -> None:
        self.members.insert(0, json.loads(event.model_dump_json()))
        del self.members[self.max_size :]

    async def list_recent(self, limit: int) -> list[dict]:
        return self.members[:limit]


class InMemoryPurchaseEvents:
    """Records dispatched events and feeds the recent-purchase projection."""

    def __init__(self, feed: InMemoryRecentPurchaseFeed | None = None):
        self.feed = feed
        self.dispatched: list[PurchaseEvent] = []

    async def dispatch(self, event: PurchaseEvent) -> None:
        self.dispatched.append(event)
        if self.feed is not None:
            self.feed.record(event)


class InMemoryCardStore:
    def __init__(self):
        self.amounts: dict[int, dict[int, int]] = {}
        self.names: dict[int, dict[int, str]] = {}

    async def get(self, user_id: int) -> CardResponse:
        amounts = self.amounts.get(user_id, {})
        names = self.names.get(user_id, {})
        items = [
            CardItem(
                product_id=product_id,
                product_name=names.get(product_id),
                amount=amount,
            )
            for product_id, amount in sorted(amounts.items())
        ]
        return CardResponse(
            user_id=user_id,
            items=items,
            total_items=sum(item.amount for item in items),
        )

    async def apply_add(self, event: CardEvent) -> int:
        if event.product_id is None:
            return 0
        amounts = self.amounts.setdefault(event.user_id, {})
        amounts[event.product_id] = amounts.get(event.product_id, 0) + event.amount
        if event.product_name:
            self.names.setdefault(event.user_id, {})[event.product_id] = event.product_name
        return amounts[event.product_id]

    async def apply_remove(self, event: CardEvent) -> None:
        if event.product_id is None:
            return
        self.amounts.get(event.user_id, {}).pop(event.product_id, None)
        self.names.get(event.user_id, {}).pop(event.product_id, None)

    async def clear(self, user_id: int) -> None:
        self.amounts.pop(user_id, None)
        self.names.pop(user_id, None)


class InMemoryEventCompletion:
    def __init__(self):
        self.claimed: set[str] = set()
        self.applied: set[str] = set()

    async def try_claim(self, event_id: str) -> bool:
        if event_id in self.claimed:
            return False
        self.claimed.add(event_id)
        return True

    async def mark_applied(self, event_id: str) -> None:
        self.applied.add(event_id)

    async def wait_applied(self, event_id: str, timeout_s: float = 2.0) -> None:
        if event_id not in self.applied:
            raise TimeoutError(f"Card event {event_id} was not applied in time")

    async def release_claim(self, event_id: str) -> None:
        self.claimed.discard(event_id)


class LoopbackCardEventPublisher:
    """Publishes by running the real subscriber handler inline.

    Mirrors production ordering: publish, subscriber applies the event, then the
    applied marker becomes visible to the waiting request.
    """

    def __init__(self, handler: RedisPubSub, channel: str = CARD_CHANNEL):
        self.handler = handler
        self.channel = channel
        self.published: list[CardEvent] = []

    async def publish(self, event: CardEvent) -> str:
        self.published.append(event)
        await self.handler.handle_message(event.model_dump_json())
        return self.channel


class ScriptedCardEventStream:
    def __init__(self, messages: list[str | None] | None = None):
        self.messages_to_emit = messages if messages is not None else []

    async def messages(self) -> AsyncIterator[str | None]:
        for message in self.messages_to_emit:
            yield message


class InMemoryPurchaseEventSource:
    """Hands out one event per read, then idles like a blocking XREAD would."""

    def __init__(self, events: list[PurchaseEvent] | None = None, idle_delay: float = 0.01):
        self.pending = list(events) if events else []
        self.idle_delay = idle_delay
        self.read_calls: list[str] = []
        self._next_id = 0

    async def read(self, last_id: str) -> list[tuple[str, PurchaseEvent]]:
        self.read_calls.append(last_id)
        if not self.pending:
            await asyncio.sleep(self.idle_delay)
            return []
        self._next_id += 1
        return [(f"{self._next_id}-0", self.pending.pop(0))]


class InMemoryConsumerLeadership:
    def __init__(self, acquired: bool = True, refresh_results: list[bool] | None = None):
        self.acquired = acquired
        self.refresh_results = refresh_results
        self.tokens: list[str] = []
        self.refresh_calls: list[str] = []
        self.released: list[str] = []

    async def acquire(self, token: str) -> bool:
        self.tokens.append(token)
        return self.acquired

    async def refresh(self, token: str) -> bool:
        self.refresh_calls.append(token)
        if self.refresh_results is None:
            return True
        return self.refresh_results.pop(0) if self.refresh_results else False

    async def release(self, token: str) -> None:
        self.released.append(token)


@dataclass
class FakeAdapters:
    """Drop-in stand-in for `RedisAdapters` used by the composition root."""

    product_cache: InMemoryProductCache = field(default_factory=InMemoryProductCache)
    purchase_coordinator: InMemoryPurchaseCoordinator = field(
        default_factory=InMemoryPurchaseCoordinator
    )
    recent_purchases: InMemoryRecentPurchaseFeed = field(
        default_factory=InMemoryRecentPurchaseFeed
    )
    purchase_events: InMemoryPurchaseEvents = field(default=None)  # type: ignore[assignment]
    card_store: InMemoryCardStore = field(default_factory=InMemoryCardStore)
    event_completion: InMemoryEventCompletion = field(default_factory=InMemoryEventCompletion)
    card_publisher: LoopbackCardEventPublisher = field(default=None)  # type: ignore[assignment]
    card_event_stream: ScriptedCardEventStream = field(default_factory=ScriptedCardEventStream)
    purchase_event_source: InMemoryPurchaseEventSource = field(
        default_factory=InMemoryPurchaseEventSource
    )
    consumer_leadership: InMemoryConsumerLeadership = field(
        default_factory=InMemoryConsumerLeadership
    )

    def __post_init__(self) -> None:
        if self.purchase_events is None:
            self.purchase_events = InMemoryPurchaseEvents(feed=self.recent_purchases)
        if self.card_publisher is None:
            handler = RedisPubSub(
                store=self.card_store,
                completion=self.event_completion,
                channel=CARD_CHANNEL,
            )
            self.card_publisher = LoopbackCardEventPublisher(handler)
