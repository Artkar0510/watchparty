from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class GenreOut(BaseModel):
    id: UUID
    name: str
    description: str | None = None

    model_config = {"from_attributes": True}


class FilmCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    rating: float | None = Field(default=None, ge=0, le=10)
    type: str = Field(default="movie", pattern="^(movie|tv_show)$")
    video_url: str = ""
    genre_ids: list[UUID] = Field(default_factory=list)


class FilmOut(BaseModel):
    id: UUID
    title: str
    description: str | None = None
    rating: float | None = None
    type: str
    video_url: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FilmDetailOut(FilmOut):
    genres: list[GenreOut] = Field(default_factory=list)


class FilmSearchResult(BaseModel):
    id: str
    title: str
    description: str | None = None
    rating: float | None = None
    type: str
    genres: list[str] = Field(default_factory=list)


class WatchlistItemOut(BaseModel):
    id: UUID
    film_work_id: UUID
    added_at: datetime

    model_config = {"from_attributes": True}


class MatchResult(BaseModel):
    film: FilmOut
    matched_friend_ids: list[str]
