"""
Session state is stored in Redis:
  session:{id} → hash with film_id, host_id, state, position, created_at
  session:{id}:participants → set of user_id strings
  session:{id}:chat → list of JSON-encoded chat messages (last 200)
"""
import json
from datetime import datetime, timezone
from uuid import uuid4

from db.redis import get_redis
from core.settings import get_settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_session(film_id: str, host_id: str, invited: list[str]) -> dict:
    settings = get_settings()
    redis = get_redis()
    session_id = str(uuid4())
    now = _now()

    await redis.hset(f"session:{session_id}", mapping={
        "film_id": film_id,
        "host_id": host_id,
        "state": "paused",
        "position": "0.0",
        "created_at": now,
    })
    await redis.expire(f"session:{session_id}", settings.app.session_ttl)

    participants = [host_id] + invited
    if participants:
        await redis.sadd(f"session:{session_id}:participants", *participants)
        await redis.expire(f"session:{session_id}:participants", settings.app.session_ttl)

    return await get_session(session_id)


async def get_session(session_id: str) -> dict | None:
    redis = get_redis()
    data = await redis.hgetall(f"session:{session_id}")
    if not data:
        return None
    participants = list(await redis.smembers(f"session:{session_id}:participants"))
    return {
        "session_id": session_id,
        "film_id": data["film_id"],
        "host_id": data["host_id"],
        "state": data["state"],
        "position": float(data["position"]),
        "participants": participants,
        "created_at": data["created_at"],
    }


async def update_playback(session_id: str, state: str, position: float) -> None:
    redis = get_redis()
    await redis.hset(f"session:{session_id}", mapping={
        "state": state,
        "position": str(position),
    })


async def add_participant(session_id: str, user_id: str) -> None:
    redis = get_redis()
    await redis.sadd(f"session:{session_id}:participants", user_id)


async def remove_participant(session_id: str, user_id: str) -> None:
    redis = get_redis()
    await redis.srem(f"session:{session_id}:participants", user_id)


async def add_chat_message(session_id: str, user_id: str, text: str) -> dict:
    redis = get_redis()
    msg = {"user_id": user_id, "text": text, "timestamp": _now()}
    await redis.rpush(f"session:{session_id}:chat", json.dumps(msg))
    await redis.ltrim(f"session:{session_id}:chat", -200, -1)
    return msg


async def get_chat_history(session_id: str, last_n: int = 50) -> list[dict]:
    redis = get_redis()
    raw = await redis.lrange(f"session:{session_id}:chat", -last_n, -1)
    return [json.loads(m) for m in raw]


async def publish_event(session_id: str, event: dict) -> None:
    redis = get_redis()
    await redis.publish(f"session:{session_id}:events", json.dumps(event))
