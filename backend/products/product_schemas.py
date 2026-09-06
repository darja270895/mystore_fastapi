from pydantic import BaseModel

class ProductMixin:
    """ Общие поля для всех DTO продукта. DRY принцип"""
    name: str
    stock: int
    price: int

class ProductCreate(ProductMixin, BaseModel):
    """ DTO """
    ...

class ProductResponse(ProductMixin, BaseModel):
    id: int

    #allows Pydantic to construct the schema from SQLAlchemy object (ORM -> DTO)
    model_config = {
        "from_attributes": True
    }