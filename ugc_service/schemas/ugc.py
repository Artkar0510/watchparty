from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LikeOut(BaseModel):
    film_id: UUID
    user_id: UUID
    created_at: datetime


class LikeStats(BaseModel):
    film_id: UUID
    likes_count: int


class BookmarkCreate(BaseModel):
    film_id: UUID


class BookmarkOut(BaseModel):
    film_id: UUID
    user_id: UUID
    created_at: datetime


class ReviewCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    rating: int | None = Field(default=None, ge=1, le=10)


class ReviewOut(BaseModel):
    id: str
    film_id: UUID
    user_id: UUID
    text: str
    rating: int | None = None
    created_at: datetime
