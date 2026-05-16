"""RabbitMQ event publisher for together-service.

Failures are logged but never raised — session creation must succeed even if
the broker is unavailable.
"""
import json
import logging

import aio_pika

from core.settings import get_settings
from core.utils import utc_now

logger = logging.getLogger(__name__)

EXCHANGE = "together.events"

_connection: aio_pika.RobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None
# Cached exchange reference — declared once at startup so publish() doesn't
# round-trip to the broker via channel.get_exchange() on every call.
_exchange: aio_pika.abc.AbstractExchange | None = None


async def init_broker() -> None:
    global _connection, _channel, _exchange
    settings = get_settings()
    if not settings.rabbit.enabled:
        return
    try:
        _connection = await aio_pika.connect_robust(settings.rabbit.url, timeout=5)
        _channel = await _connection.channel()
        _exchange = await _channel.declare_exchange(
            EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
        )
        logger.info("together.events publisher connected")
    except Exception:
        logger.exception("RabbitMQ connect failed — together.events disabled")
        _connection = None
        _channel = None
        _exchange = None


async def close_broker() -> None:
    global _connection, _channel, _exchange
    if _connection:
        await _connection.close()
    _connection = None
    _channel = None
    _exchange = None


async def publish(routing_key: str, payload: dict) -> None:
    if _exchange is None:
        return
    try:
        body = {**payload, "emitted_at": utc_now()}
        message = aio_pika.Message(
            body=json.dumps(body, default=str).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await _exchange.publish(message, routing_key=routing_key)
    except Exception:
        logger.exception("Failed to publish %s", routing_key)
