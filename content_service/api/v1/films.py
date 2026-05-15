import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from core.settings import get_settings
from db.elasticsearch import MOVIES_INDEX, get_es
from db.postgres import get_pool
from db.redis import get_redis
from schemas.film import FilmCreate, FilmDetailOut, FilmOut, FilmSearchResult

router = APIRouter()


@router.get("", response_model=list[FilmOut])
async def list_films(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="-rating"),
):
    settings = get_settings()
    cache_key = f"films:list:{page}:{page_size}:{sort}"
    redis = get_redis()
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    order_col = "rating"
    order_dir = "DESC" if sort.startswith("-") else "ASC"
    col_name = sort.lstrip("-")
    allowed_sorts = {"rating", "title", "created_at"}
    if col_name not in allowed_sorts:
        raise HTTPException(status_code=400, detail=f"Invalid sort field. Allowed: {allowed_sorts}")
    order_col = col_name

    offset = (page - 1) * page_size
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT id, title, description, rating, type, created_at, updated_at "
            f"FROM film_work ORDER BY {order_col} {order_dir} LIMIT $1 OFFSET $2",
            page_size, offset,
        )

    result = [dict(r) for r in rows]
    await redis.setex(cache_key, settings.app.cache_expire_seconds, json.dumps(result, default=str))
    return result


@router.get("/search", response_model=list[FilmSearchResult])
async def search_films(
    query: str = Query(min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    es = get_es()
    body = {
        "from": (page - 1) * page_size,
        "size": page_size,
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["title^2", "description", "genres"],
                "fuzziness": "AUTO",
            }
        },
    }
    resp = await es.search(index=MOVIES_INDEX, body=body)
    hits = resp["hits"]["hits"]
    return [{"id": h["_id"], **h["_source"]} for h in hits]


@router.get("/{film_id}", response_model=FilmDetailOut)
async def get_film(film_id: UUID):
    redis = get_redis()
    cache_key = f"film:{film_id}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    pool = get_pool()
    async with pool.acquire() as conn:
        film = await conn.fetchrow(
            "SELECT id, title, description, rating, type, created_at, updated_at FROM film_work WHERE id=$1",
            film_id,
        )
        if not film:
            raise HTTPException(status_code=404, detail="Film not found")

        genres = await conn.fetch(
            """SELECT g.id, g.name, g.description FROM genre g
               JOIN genre_film_work gfw ON gfw.genre_id=g.id
               WHERE gfw.film_work_id=$1""",
            film_id,
        )

    result = {**dict(film), "genres": [dict(g) for g in genres]}
    settings = get_settings()
    await redis.setex(cache_key, settings.app.cache_expire_seconds, json.dumps(result, default=str))
    return result


@router.post("", response_model=FilmOut, status_code=status.HTTP_201_CREATED)
async def create_film(body: FilmCreate):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            film = await conn.fetchrow(
                """INSERT INTO film_work (title, description, rating, type)
                   VALUES ($1, $2, $3, $4)
                   RETURNING id, title, description, rating, type, created_at, updated_at""",
                body.title, body.description, body.rating, body.type,
            )
            film_id = film["id"]
            for genre_id in body.genre_ids:
                await conn.execute(
                    "INSERT INTO genre_film_work (film_work_id, genre_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    film_id, genre_id,
                )

    es = get_es()
    await es.index(
        index=MOVIES_INDEX,
        id=str(film_id),
        document={
            "title": body.title,
            "description": body.description,
            "rating": body.rating,
            "type": body.type,
            "genres": [str(g) for g in body.genre_ids],
            "updated_at": dict(film)["updated_at"].isoformat(),
        },
    )
    return dict(film)
