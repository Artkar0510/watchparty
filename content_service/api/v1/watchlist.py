from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from db.postgres import get_pool
from schemas.film import FilmOut, WatchlistItemOut
from utils.auth import get_current_user_id

router = APIRouter()


class WatchlistAdd(BaseModel):
    film_work_id: UUID


@router.get("", response_model=list[FilmOut])
async def get_my_watchlist(user_id: UUID = Depends(get_current_user_id)):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT fw.id, fw.title, fw.description, fw.rating, fw.type, fw.created_at, fw.updated_at
               FROM film_work fw
               JOIN watchlist w ON w.film_work_id=fw.id
               WHERE w.user_id=$1
               ORDER BY w.added_at DESC""",
            user_id,
        )
    return [dict(r) for r in rows]


@router.post("", response_model=WatchlistItemOut, status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    body: WatchlistAdd,
    user_id: UUID = Depends(get_current_user_id),
):
    pool = get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT id FROM film_work WHERE id=$1", body.film_work_id
        )
        if not exists:
            raise HTTPException(status_code=404, detail="Film not found")

        try:
            row = await conn.fetchrow(
                """INSERT INTO watchlist (user_id, film_work_id)
                   VALUES ($1, $2) RETURNING id, film_work_id, added_at""",
                user_id, body.film_work_id,
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Film already in watchlist")
    return dict(row)


@router.delete("/{film_work_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(
    film_work_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
):
    pool = get_pool()
    async with pool.acquire() as conn:
        deleted = await conn.fetchval(
            "DELETE FROM watchlist WHERE user_id=$1 AND film_work_id=$2 RETURNING id",
            user_id, film_work_id,
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="Film not in watchlist")


@router.get("/user/{user_id}", response_model=list[str])
async def get_user_watchlist_ids(user_id: UUID):
    """Internal: returns film IDs for a given user (used for match calculation)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT film_work_id FROM watchlist WHERE user_id=$1", user_id
        )
    return [str(r["film_work_id"]) for r in rows]
