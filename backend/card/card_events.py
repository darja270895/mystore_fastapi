from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class CardEvent(BaseModel):
    """Application event describing a requested Card mutation."""

    event_id: str = Field(default_factory=lambda: uuid4().hex)
    action: Literal["add", "remove", "clear"]
    user_id: int
    product_id: int | None = None
    amount: int = 1
    product_name: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
