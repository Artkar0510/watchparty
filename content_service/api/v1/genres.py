from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from db.postgres import get_pool
from schemas.film import GenreOut

router = APIRouter()


class GenreCreate(BaseModel):
    name: str
    description: str | None = None


@router.get("", response_model=list[GenreOut])
async def list_genres():
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, name, description FROM genre ORDER BY name")
    return [dict(r) for r in rows]


@router.get("/{genre_id}", response_model=GenreOut)
async def get_genre(genre_id: UUID):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, description FROM genre WHERE id=$1", genre_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="Genre not found")
    return dict(row)


@router.post("", response_model=GenreOut, status_code=status.HTTP_201_CREATED)
async def create_genre(body: GenreCreate):
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                "INSERT INTO genre (name, description) VALUES ($1, $2) RETURNING id, name, description",
                body.name, body.description,
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Genre with this name already exists")
    return dict(row)
