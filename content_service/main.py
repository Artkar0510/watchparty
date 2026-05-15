from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.v1 import v1_router
from core.settings import get_settings
from db.elasticsearch import close_elasticsearch, init_elasticsearch
from db.postgres import close_db, init_db
from db.redis import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_redis()
    await init_elasticsearch()
    yield
    await close_elasticsearch()
    await close_redis()
    await close_db()


settings = get_settings()

app = FastAPI(
    title="Content Service",
    description="Movie catalog, watchlist and social matching",
    version="1.0.0",
    debug=settings.app.debug,
    lifespan=lifespan,
)

app.include_router(v1_router, prefix=settings.app.api_v1_prefix)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "service": "content"}
