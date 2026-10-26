from __future__ import annotations

from typing import Protocol

from backend.products.product_schemas import ProductResponse


class ProductCache(Protocol):
    """Application port for cached product projections."""

    async def get(self, product_id: int) -> ProductResponse | None: ...

    async def put(self, product_id: int, product: ProductResponse) -> None: ...

    async def invalidate(self, product_id: int) -> None: ...

    async def ttl(self, product_id: int) -> int: ...
