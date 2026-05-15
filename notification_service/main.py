import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI

from api.v1 import v1_router
from core.logger import setup_logging
from core.settings import get_settings
from db.redis import close_redis, init_redis

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("notification-service API starting")
    await init_redis()
    logger.info("notification-service API ready")
    yield
    logger.info("notification-service API shutting down")
    await close_redis()


settings = get_settings()

if settings.sentry.dsn:
    sentry_sdk.init(
        dsn=settings.sentry.dsn,
        environment=settings.sentry.environment,
        traces_sample_rate=settings.sentry.traces_sample_rate,
    )

app = FastAPI(
    title="Notification Service",
    description="User notifications fed by RabbitMQ events",
    version="1.0.0",
    debug=settings.app.debug,
    lifespan=lifespan,
)

app.include_router(v1_router, prefix=settings.app.api_v1_prefix)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "service": "notification"}
