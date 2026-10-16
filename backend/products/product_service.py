import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.products.product_db_interface import ProductDbInterface
from backend.products.product_schemas import ProductCreate, ProductResponse
from fastapi import HTTPException

from backend.products.product_ports import ProductCache

""" Основная Бизнес-логика. Объединяет Интерфейс взаимодействия с БД и Бизнес-логику"""

logger = logging.getLogger(__name__)


class ProductService:

    def __init__(self, db_session: AsyncSession, cache: ProductCache | None = None):
        self.db_session = db_session
        self.cache = cache
        self.db_interface = ProductDbInterface(db_session) 

    async def create_product(self, product_data: ProductCreate):
        existing_product = await self.db_interface.get_by_name(product_name=product_data.name)
        if existing_product:
            raise HTTPException(status_code=409, detail="Product with this name already exists")
        product_obj = await self.db_interface.create_product(product_data)

        await self.db_session.commit()
        await self.db_session.refresh(product_obj) # ?????

        product_response = ProductResponse.model_validate(product_obj)
        if self.cache:
            await self.cache.put(product_obj.id, product_response)

        return product_obj

    async def get_by_name(self, product_name: str):
        product_obj = await self.db_interface.get_by_name(product_name=product_name)
        if product_obj:
            return product_obj
        raise HTTPException(status_code=404, detail="Product not found")

    async def get_by_id(self, product_id: int):
        if self.cache:
            cached_product = await self.cache.get(product_id)
            if cached_product is not None:
                return cached_product

        product_obj = await self.db_interface.get_by_id(product_id=product_id)
        if product_obj is None:
            raise HTTPException(status_code=404, detail="Product not found")

        product_response = ProductResponse.model_validate(product_obj)
        if self.cache:
            await self.cache.put(product_id, product_response)

        return product_response

    async def get_cache_ttl(self, product_id: int) -> int:
        if self.cache is None:
            raise HTTPException(status_code=503, detail="Cache unavailable")
        return await self.cache.ttl(product_id)

    async def get_all_products(self):
        return await self.db_interface.get_all()

    async def delete_product(self, product_id: int) -> ProductResponse:
        product_obj = await self.db_interface.get_by_id(product_id=product_id)
        if product_obj is None:
            raise HTTPException(status_code=404, detail="Product not found")

        product_response = ProductResponse.model_validate(product_obj)

        try:
            await self.db_interface.delete(product_obj)
            await self.db_session.commit()
        except IntegrityError:
            await self.db_session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Cannot delete product: it is referenced by purchases or stock movements",
            )

        if self.cache:
            await self.cache.invalidate(product_id)
            logger.info("Invalidated product %s cache", product_id)

        return product_response
