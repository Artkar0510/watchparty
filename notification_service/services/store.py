"""Notification storage in Redis.

  notifications:{user_id}     LIST of JSON-encoded notifications (newest first)
  notifications:{user_id}:unread  STRING (count of unread)
"""
import json
from datetime import datetime, timezone
from uuid import uuid4

from core.settings import get_settings
from db.redis import get_redis


def _key(user_id: str) -> str:
    return f"notifications:{user_id}"


def _unread_key(user_id: str) -> str:
    return f"notifications:{user_id}:unread"


async def push(user_id: str, kind: str, payload: dict) -> dict:
    settings = get_settings()
    redis = get_redis()
    notification = {
        "id": str(uuid4()),
        "kind": kind,
        "payload": payload,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read": False,
    }
    pipe = redis.pipeline()
    pipe.lpush(_key(user_id), json.dumps(notification, default=str))
    pipe.ltrim(_key(user_id), 0, settings.app.max_history - 1)
    pipe.incr(_unread_key(user_id))
    await pipe.execute()
    return notification


async def list_for(user_id: str, limit: int = 50) -> list[dict]:
    redis = get_redis()
    raw = await redis.lrange(_key(user_id), 0, limit - 1)
    return [json.loads(n) for n in raw]


async def unread_count(user_id: str) -> int:
    redis = get_redis()
    val = await redis.get(_unread_key(user_id))
    return int(val) if val else 0


async def mark_all_read(user_id: str) -> None:
    redis = get_redis()
    await redis.set(_unread_key(user_id), 0)
