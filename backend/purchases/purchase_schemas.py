from datetime import datetime

from pydantic import BaseModel, Field


class PurchaseCreate(BaseModel):
    """Body for POST /purchases/ — id is assigned by the database."""

    user_id: int
    product_id: int
    amount: int = Field(default=1, ge=1)


class PurchaseResponse(BaseModel):
    id: int
    user_id: int
    product_id: int
    amount: int
    created_at: datetime

    model_config = {"from_attributes": True}


class StockMovementResponse(BaseModel):
    id: int
    product_id: int
    delta: int
    reason: str
    purchase_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    kind: str
    payload: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
