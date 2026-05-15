import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.v1 import v1_router
from api.v1.websocket import router as ws_router
from core.logger import setup_logging
from core.settings import get_settings
from db.redis import close_redis, init_redis

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("together-service starting")
    await init_redis()
    logger.info("together-service ready")
    yield
    logger.info("together-service shutting down")
    await close_redis()


settings = get_settings()

app = FastAPI(
    title="Together Service",
    description="Real-time watch-together sessions with WebSocket synchronization",
    version="1.0.0",
    debug=settings.app.debug,
    lifespan=lifespan,
)

# REST endpoints at /api/v1/sessions/
app.include_router(v1_router, prefix=settings.app.api_v1_prefix)

# WebSocket at /ws/{session_id} (matches nginx /ws/ proxy)
app.include_router(ws_router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "service": "together"}
