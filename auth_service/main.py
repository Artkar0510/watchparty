from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.v1 import v1_router
from core.settings import get_settings
from db.postgres import close_db, init_db
from db.redis import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_redis()
    yield
    await close_redis()
    await close_db()


settings = get_settings()

app = FastAPI(
    title="Auth Service",
    description="User authentication and friendship management",
    version="1.0.0",
    debug=settings.app.debug,
    lifespan=lifespan,
)

app.include_router(v1_router, prefix=settings.app.api_v1_prefix)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "service": "auth"}
