import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.v1 import v1_router
from core.logger import setup_logging
from core.settings import get_settings
from db.postgres import close_db, init_db
from db.redis import close_redis, init_redis

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("auth-service starting")
    await init_db()
    await init_redis()
    logger.info("auth-service ready")
    yield
    logger.info("auth-service shutting down")
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
