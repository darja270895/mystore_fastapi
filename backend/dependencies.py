from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.card.card_ports import CardEventStream
from backend.card.card_service import CardService
from backend.config import settings
from backend.database import get_db
from backend.k8s.k8s_adapters import (
    RuntimeDependencyHealthAdapter,
    build_k8s_cluster_gateway,
)
from backend.k8s.k8s_ports import DependencyHealthChecker, K8sClusterGateway
from backend.k8s.k8s_service import K8sService
from backend.products.product_service import ProductService
from backend.purchases.purchase_service import PurchaseService
from backend.redis_app.adapters import RedisAdapters


def get_redis_adapters(request: Request) -> RedisAdapters | None:
    """Composition boundary: infrastructure is exposed only to providers."""
    return getattr(request.app.state, "redis_adapters", None)


def _build_purchase_service(
    db: AsyncSession,
    adapters: RedisAdapters | None,
) -> PurchaseService:
    """Inject Redis adapter instance into Purchase Service"""
    return PurchaseService(
        db_session=db,
        coordinator=adapters.purchase_coordinator if adapters else None,
        events=adapters.purchase_events if adapters else None,
        recent_feed=adapters.recent_purchases if adapters else None,
    )


def get_product_service(
    db: AsyncSession = Depends(get_db),
    adapters: RedisAdapters | None = Depends(get_redis_adapters),
) -> ProductService:
    return ProductService(
        db_session=db,
        cache=adapters.product_cache if adapters else None,
    )


def get_purchase_service(
    db: AsyncSession = Depends(get_db),
    adapters: RedisAdapters | None = Depends(get_redis_adapters),
) -> PurchaseService:
    return PurchaseService(
        db_session=db,
        coordinator=adapters.purchase_coordinator if adapters else None,
        events=adapters.purchase_events if adapters else None,
        recent_feed=adapters.recent_purchases if adapters else None,
    )


def get_card_service(
    db: AsyncSession = Depends(get_db),
    adapters: RedisAdapters | None = Depends(get_redis_adapters),
) -> CardService:
    purchase_service = _build_purchase_service(db, adapters)
    return CardService(
        db_session=db,
        store=adapters.card_store if adapters else None,
        publisher=adapters.card_publisher if adapters else None,
        completion=adapters.event_completion if adapters else None,
        purchase_creator=purchase_service,
    )


def get_card_event_stream(
    adapters: RedisAdapters | None = Depends(get_redis_adapters),
) -> CardEventStream | None:
    return adapters.card_event_stream if adapters else None


def get_k8s_cluster_gateway() -> K8sClusterGateway:
    return build_k8s_cluster_gateway()


def get_dependency_health_checker(
    request: Request,
    db: AsyncSession = Depends(get_db),
    adapters: RedisAdapters | None = Depends(get_redis_adapters),
) -> DependencyHealthChecker:
    redis_client = getattr(request.app.state, "redis", None)
    redis_ping = None
    if redis_client is not None and hasattr(redis_client, "ping"):
        redis_ping = redis_client.ping
    elif adapters is not None:

        async def _fake_redis_ping() -> bool:
            return True

        redis_ping = _fake_redis_ping

    startup_complete = bool(getattr(request.app.state, "k8s_started", True))
    stream_consumer_active = bool(
        getattr(request.app.state, "stream_consumer_active", False)
    )
    return RuntimeDependencyHealthAdapter(
        db_session=db,
        redis_ping=redis_ping,
        redis_enabled=settings.USE_REDIS,
        startup_complete=startup_complete,
        stream_consumer_active=stream_consumer_active,
    )


def get_k8s_service(
    health_checker: DependencyHealthChecker = Depends(get_dependency_health_checker),
    cluster_gateway: K8sClusterGateway = Depends(get_k8s_cluster_gateway),
) -> K8sService:
    return K8sService(
        health_checker=health_checker,
        cluster_gateway=cluster_gateway,
    )

