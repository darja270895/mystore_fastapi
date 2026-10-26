"""Centralized Redis key naming — avoids magic strings across services."""


def product_cache_key(product_id: int) -> str:
    return f"cache:product:{product_id}"


def stock_lock_key(product_id: int) -> str:
    return f"lock:stock:{product_id}"


def buy_rate_limit_key(user_id: int) -> str:
    return f"ratelimit:buy:{user_id}"


def card_key(user_id: int) -> str:
    """Redis HASH: field=product_id, value=amount."""
    return f"card:user:{user_id}"


def card_event_claim_key(event_id: str) -> str:
    """Claim lock so only one worker applies a given CardEvent."""
    return f"card:claim:{event_id}"


def card_event_applied_key(event_id: str) -> str:
    """Set after HASH write succeeds — publisher polls this key."""
    return f"card:applied:{event_id}"
