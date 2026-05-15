"""RabbitMQ event publisher for together-service.

Failures are logged but never raised — session creation must succeed even if
the broker is unavailable.
"""
import json
import logging
from datetime import datetime, timezone

import aio_pika

from core.settings import get_settings

logger = logging.getLogger(__name__)

EXCHANGE = "together.events"

_connection: aio_pika.RobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None


async def init_broker() -> None:
    global _connection, _channel
    settings = get_settings()
    if not settings.rabbit.enabled:
        return
    try:
        _connection = await aio_pika.connect_robust(settings.rabbit.url, timeout=5)
        _channel = await _connection.channel()
        await _channel.declare_exchange(EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)
        logger.info("together.events publisher connected")
    except Exception:
        logger.exception("RabbitMQ connect failed — together.events disabled")
        _connection = None
        _channel = None


async def close_broker() -> None:
    global _connection, _channel
    if _connection:
        await _connection.close()
    _connection = None
    _channel = None


async def publish(routing_key: str, payload: dict) -> None:
    if _channel is None:
        return
    try:
        body = {**payload, "emitted_at": datetime.now(timezone.utc).isoformat()}
        message = aio_pika.Message(
            body=json.dumps(body, default=str).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        exchange = await _channel.get_exchange(EXCHANGE)
        await exchange.publish(message, routing_key=routing_key)
    except Exception:
        logger.exception("Failed to publish %s", routing_key)
