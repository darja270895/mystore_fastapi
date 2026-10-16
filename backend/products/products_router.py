from fastapi import APIRouter, Depends

from backend.dependencies import get_product_service
from backend.products.product_schemas import ProductResponse, ProductCreate
from backend.products.product_service import ProductService

""" 
Отвечает за HTTP.
Объединяет Бизнес-логику и инфраструктуру (запросы к БД)
HTTP Request -> Schema -> Service -> Response
"""

router = APIRouter(
    prefix="/products",
    tags=["Products"]
)


@router.post("/", response_model=ProductResponse)
async def create_product(product_data: ProductCreate, service: ProductService = Depends(get_product_service)):
    return await service.create_product(product_data=product_data)


@router.get("/", response_model=list[ProductResponse])
async def get_all_products(service: ProductService = Depends(get_product_service)):
    return await service.get_all_products()

@router.delete("/{product_id}", response_model=ProductResponse)
async def delete_product(product_id: int, service: ProductService = Depends(get_product_service)):
    return await service.delete_product(product_id=product_id)

@router.get("/cache/{product_id}/ttl")
async def get_cache_ttl(
        product_id: int,
        service: ProductService = Depends(get_product_service),
):
    return await service.get_cache_ttl(product_id)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product_by_id(product_id: int, service: ProductService = Depends(get_product_service)):
    return await service.get_by_id(product_id=product_id)