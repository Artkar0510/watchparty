from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from db.postgres import get_pool
from schemas.film import FilmOut, MatchResult
from utils.auth import get_current_user_id, get_friend_ids

router = APIRouter()
bearer = HTTPBearer()


@router.get("", response_model=list[MatchResult])
async def find_matches(
    request: Request,
    user_id: UUID = Depends(get_current_user_id),
):
    """Find films that are in both current user's and at least one friend's watchlist."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()

    friend_ids = await get_friend_ids(user_id, token)
    if not friend_ids:
        return []

    pool = get_pool()
    async with pool.acquire() as conn:
        my_films = await conn.fetch(
            "SELECT film_work_id FROM watchlist WHERE user_id=$1", user_id
        )
        my_film_ids = {str(r["film_work_id"]) for r in my_films}

        if not my_film_ids:
            return []

        friend_watchlists: dict[str, set[str]] = {}
        for fid in friend_ids:
            rows = await conn.fetch(
                "SELECT film_work_id FROM watchlist WHERE user_id=$1", UUID(fid)
            )
            friend_watchlists[fid] = {str(r["film_work_id"]) for r in rows}

        matches: dict[str, list[str]] = {}
        for fid, friend_films in friend_watchlists.items():
            common = my_film_ids & friend_films
            for film_id in common:
                matches.setdefault(film_id, []).append(fid)

        if not matches:
            return []

        match_ids = [UUID(fid) for fid in matches]
        films = await conn.fetch(
            """SELECT id, title, description, rating, type, created_at, updated_at
               FROM film_work WHERE id = ANY($1::uuid[])""",
            match_ids,
        )

    result = []
    for film in films:
        film_dict = dict(film)
        fid_str = str(film_dict["id"])
        result.append(
            MatchResult(
                film=FilmOut(**film_dict),
                matched_friend_ids=matches[fid_str],
            )
        )

    result.sort(key=lambda x: len(x.matched_friend_ids), reverse=True)
    return result
