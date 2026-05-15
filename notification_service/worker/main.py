"""RabbitMQ consumer that turns inter-service events into per-user notifications.

Bound queues:
  ugc.events           routing keys: like.created, review.created
  together.events      routing keys: session.created
  auth.events          routing keys: friend.request, friend.accepted

Each event determines its target user (or fans out to a list) and pushes a
notification through services.store.
"""
import asyncio
import json
import logging
import signal

import aio_pika
import sentry_sdk

from core.logger import setup_logging
from core.settings import get_settings
from db.redis import close_redis, init_redis
from services import store

setup_logging()
logger = logging.getLogger("notification.worker")

EXCHANGES = {
    "ugc.events": ["like.created", "review.created"],
    "together.events": ["session.created", "session.invite"],
    "auth.events": ["friend.request", "friend.accepted"],
}


def _resolve_targets(routing_key: str, body: dict) -> list[str]:
    """Map an event into the list of user_ids who should be notified."""
    if routing_key == "like.created":
        # Films don't have a single owner; we skip this for now.
        return []
    if routing_key == "review.created":
        return []
    if routing_key in ("session.created", "session.invite"):
        return list(body.get("invited_user_ids", []))
    if routing_key == "friend.request":
        return [body["addressee_id"]] if body.get("addressee_id") else []
    if routing_key == "friend.accepted":
        return [body["requester_id"]] if body.get("requester_id") else []
    return []


async def _handle(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process(requeue=False):
        try:
            body = json.loads(message.body.decode())
        except json.JSONDecodeError:
            logger.warning("Discarding non-JSON message: %r", message.body[:200])
            return

        routing_key = message.routing_key or ""
        targets = _resolve_targets(routing_key, body)
        if not targets:
            logger.debug("No targets for %s, skipping", routing_key)
            return

        for user_id in targets:
            await store.push(user_id, kind=routing_key, payload=body)
        logger.info("Notified %d user(s) for %s", len(targets), routing_key)


async def _bind_exchange(channel: aio_pika.abc.AbstractChannel,
                         exchange_name: str, routing_keys: list[str]) -> aio_pika.abc.AbstractQueue:
    exchange = await channel.declare_exchange(exchange_name, aio_pika.ExchangeType.TOPIC, durable=True)
    queue = await channel.declare_queue(f"notify.{exchange_name}", durable=True)
    for rk in routing_keys:
        await queue.bind(exchange, routing_key=rk)
    return queue


async def run() -> None:
    settings = get_settings()
    if settings.sentry.dsn:
        sentry_sdk.init(
            dsn=settings.sentry.dsn,
            environment=settings.sentry.environment,
            traces_sample_rate=settings.sentry.traces_sample_rate,
        )

    await init_redis()

    connection = await aio_pika.connect_robust(settings.rabbit.url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=32)

    queues: list[aio_pika.abc.AbstractQueue] = []
    for exchange_name, keys in EXCHANGES.items():
        queue = await _bind_exchange(channel, exchange_name, keys)
        await queue.consume(_handle)
        queues.append(queue)

    logger.info("notification worker subscribed to %d exchange(s)", len(queues))

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    try:
        await stop_event.wait()
    finally:
        logger.info("notification worker stopping")
        await connection.close()
        await close_redis()


if __name__ == "__main__":
    asyncio.run(run())
