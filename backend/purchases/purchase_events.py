from datetime import datetime, timezone

from pydantic import BaseModel, Field


class PurchaseEvent(BaseModel):
    """Application event emitted after a purchase is committed."""

    purchase_id: int
    user_id: int
    product_id: int
    amount: int
    product_name: str
    total_price: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
