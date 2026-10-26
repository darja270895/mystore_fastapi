"""ProductService unit tests: cache-aside behaviour and error mapping."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from backend import models
from backend.products.product_schemas import ProductCreate, ProductResponse
from backend.products.product_service import ProductService
from backend.tests.fakes import InMemoryProductCache


def make_product(product_id: int = 1, name: str = "Mouse", stock: int = 5, price: float = 10.0):
    product = models.Product(name=name, stock=stock, price=price)
    product.id = product_id
    return product


@pytest.fixture
def cache() -> InMemoryProductCache:
    return InMemoryProductCache()


@pytest.fixture
def service(cache) -> ProductService:
    service = ProductService(db_session=AsyncMock(), cache=cache)
    service.db_interface = AsyncMock()
    return service


async def test_create_product_rejects_duplicate_name(service):
    service.db_interface.get_by_name.return_value = make_product()

    with pytest.raises(HTTPException) as exc_info:
        await service.create_product(ProductCreate(name="Mouse", stock=1, price=5))

    assert exc_info.value.status_code == 409
    service.db_interface.create_product.assert_not_awaited()


async def test_create_product_commits_and_warms_cache(service, cache):
    service.db_interface.get_by_name.return_value = None
    service.db_interface.create_product.return_value = make_product(product_id=7)

    created = await service.create_product(ProductCreate(name="Mouse", stock=5, price=10))

    assert created.id == 7
    service.db_session.commit.assert_awaited_once()
    service.db_session.refresh.assert_awaited_once()
    assert cache.put_calls == [7]


async def test_create_product_works_without_cache():
    service = ProductService(db_session=AsyncMock(), cache=None)
    service.db_interface = AsyncMock()
    service.db_interface.get_by_name.return_value = None
    service.db_interface.create_product.return_value = make_product()

    assert (await service.create_product(ProductCreate(name="Mouse", stock=1, price=2))).id == 1


async def test_get_by_id_returns_cached_projection_without_touching_db(service, cache):
    cached = ProductResponse(id=3, name="Cached", stock=2, price=9)
    cache.values[3] = cached

    assert await service.get_by_id(3) is cached
    service.db_interface.get_by_id.assert_not_awaited()


async def test_get_by_id_falls_back_to_db_and_populates_cache(service, cache):
    service.db_interface.get_by_id.return_value = make_product(product_id=4, name="Screen")

    result = await service.get_by_id(4)

    assert isinstance(result, ProductResponse)
    assert result.name == "Screen"
    assert cache.put_calls == [4]


async def test_get_by_id_raises_404_when_missing(service):
    service.db_interface.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await service.get_by_id(99)

    assert exc_info.value.status_code == 404


async def test_get_by_name_returns_product_or_404(service):
    service.db_interface.get_by_name.return_value = make_product(name="Desk")
    assert (await service.get_by_name("Desk")).name == "Desk"

    service.db_interface.get_by_name.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.get_by_name("Nope")
    assert exc_info.value.status_code == 404


async def test_get_cache_ttl_delegates_to_cache(service, cache):
    cache.values[5] = ProductResponse(id=5, name="X", stock=1, price=1)

    assert await service.get_cache_ttl(5) == cache.ttl_seconds


async def test_get_cache_ttl_requires_cache():
    service = ProductService(db_session=AsyncMock(), cache=None)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_cache_ttl(1)

    assert exc_info.value.status_code == 503


async def test_get_all_products_delegates_to_repository(service):
    service.db_interface.get_all.return_value = [make_product()]

    assert len(await service.get_all_products()) == 1


async def test_delete_product_invalidates_cache(service, cache):
    service.db_interface.get_by_id.return_value = make_product(product_id=8, name="Lamp")
    cache.values[8] = ProductResponse(id=8, name="Lamp", stock=1, price=3)

    deleted = await service.delete_product(8)

    assert deleted.name == "Lamp"
    assert cache.invalidated == [8]
    service.db_session.commit.assert_awaited_once()


async def test_delete_product_raises_404_when_missing(service):
    service.db_interface.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_product(123)

    assert exc_info.value.status_code == 404


async def test_delete_product_maps_integrity_error_to_409(service):
    service.db_interface.get_by_id.return_value = make_product(product_id=9)
    service.db_interface.delete.side_effect = IntegrityError("stmt", {}, Exception("fk"))

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_product(9)

    assert exc_info.value.status_code == 409
    service.db_session.rollback.assert_awaited_once()
