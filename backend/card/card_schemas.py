from pydantic import BaseModel, Field


class CardAdd(BaseModel):
    user_id: int
    product_id: int
    amount: int = Field(default=1, ge=1)


class CardRemove(BaseModel):
    user_id: int
    product_id: int


class CardItem(BaseModel):
    product_id: int
    product_name: str | None = None
    amount: int


class CardResponse(BaseModel):
    user_id: int
    items: list[CardItem]
    total_items: int


class CardPublishResponse(BaseModel):
    """Returned after publishing a CardEvent (subscriber writes Redis HASH)."""

    status: str = "queued"
    event_id: str
    channel: str
    card: CardResponse
