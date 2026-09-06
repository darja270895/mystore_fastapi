import pdb

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.products.product_schemas import ProductResponse, ProductCreate
from backend.products.product_service import ProductService
from backend.redis_app.redis_service import RedisService, get_redis_service

""" 
Отвечает за HTTP.
Объединяет Бизнес-логику и инфраструктуру (запросы к БД)
HTTP Request -> Schema -> Service -> Response
"""

router = APIRouter(
    prefix="/products",
    tags=["Products"]
)


def get_product_service(
        db: AsyncSession = Depends(get_db),
        redis: RedisService =Depends(get_redis_service)) -> ProductService:

    return ProductService(db_session=db, redis=redis)


@router.post("/", response_model=ProductResponse)
async def create_product(product_data: ProductCreate, service: ProductService = Depends(get_product_service)):
    return await service.create_product(product_data=product_data)


@router.get("/", response_model=list[ProductResponse])
async def get_all_products(service: ProductService = Depends(get_product_service)):
    return await service.get_all_products()


# @router.get("/{product_name}", response_model=ProductResponse)
# async def get_product(product_name: str, service: ProductService = Depends(get_product_service)):
#     return await service.get_by_name(product_name=product_name)

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product_by_id(product_id: int, service: ProductService = Depends(get_product_service)):
    return await service.get_by_id(product_id=product_id)

@router.get("/cache/{product_id}/ttl")
async def get_cache_ttl(
        product_id: int,
        redis: RedisService = Depends(get_redis_service),
):
    return await redis.ttl_check(
        f"product_{product_id}"
    )