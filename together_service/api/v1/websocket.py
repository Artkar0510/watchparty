"""
WebSocket endpoint for real-time watch synchronization.

Architecture: every event flows through Redis pub/sub. Each running instance of
together-service subscribes to a per-session channel and forwards messages to
its locally-connected WebSocket clients only. This makes the service horizontally
scalable — clients in session X may be split across multiple instances.

Protocol (JSON messages):
  Client → Server:
    {"type": "play",  "position": 12.5}
    {"type": "pause", "position": 12.5}
    {"type": "seek",  "position": 60.0}
    {"type": "chat",  "text": "Hello!"}
    {"type": "sync"}                       — request current state (server replies privately)

  Server → Client (broadcast via Redis):
    {"type": "join",  "user_id": "...", "session": {...}, "timestamp": "..."}
    {"type": "play",  "user_id": "...", "position": 12.5, "timestamp": "..."}
    {"type": "pause", "user_id": "...", "position": 12.5, "timestamp": "..."}
    {"type": "seek",  "user_id": "...", "position": 60.0, "timestamp": "..."}
    {"type": "chat",  "user_id": "...", "text": "...", "timestamp": "..."}
    {"type": "leave", "user_id": "...", "timestamp": "..."}
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.settings import get_settings
from db.redis import get_redis
from services import session_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# Local connections only — each instance tracks its own clients.
# session_id -> {user_id -> WebSocket}
_local_connections: dict[str, dict[str, WebSocket]] = {}
# session_id -> asyncio.Task running the Redis subscriber
_subscribers: dict[str, asyncio.Task] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _channel(session_id: str) -> str:
    return f"session:{session_id}:events"


async def verify_token(token: str) -> str | None:
    settings = get_settings()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.auth.service_url}/api/v1/auth/verify",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
        if resp.status_code == 200:
            return resp.json()["user_id"]
    except httpx.HTTPError as exc:
        logger.warning("Token verification failed: %s", exc)
    return None


async def _fanout_to_local(session_id: str, payload: str) -> None:
    """Send raw JSON payload to all local WS clients in the given session."""
    connections = _local_connections.get(session_id, {})
    dead: list[str] = []
    for uid, ws in list(connections.items()):
        try:
            await ws.send_text(payload)
        except Exception as exc:
            logger.info("WS send failed for user=%s session=%s: %s", uid, session_id, exc)
            dead.append(uid)
    for uid in dead:
        connections.pop(uid, None)


async def _redis_subscriber(session_id: str) -> None:
    """Long-running task: subscribes to the session channel and fans out to local clients.

    The subscriber lives until the last local client disconnects from this instance.
    """
    redis = get_redis()
    pubsub = redis.pubsub()
    channel = _channel(session_id)
    await pubsub.subscribe(channel)
    logger.info("Subscribed to %s", channel)
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            await _fanout_to_local(session_id, message["data"])
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Redis subscriber crashed for session=%s", session_id)
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except Exception:
            pass
        logger.info("Unsubscribed from %s", channel)


def _ensure_subscriber(session_id: str) -> None:
    task = _subscribers.get(session_id)
    if task is None or task.done():
        _subscribers[session_id] = asyncio.create_task(_redis_subscriber(session_id))


async def _stop_subscriber_if_idle(session_id: str) -> None:
    if not _local_connections.get(session_id):
        _local_connections.pop(session_id, None)
        task = _subscribers.pop(session_id, None)
        if task and not task.done():
            task.cancel()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, token: str = ""):
    user_id = await verify_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    session = await session_manager.get_session(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    if user_id not in session["participants"]:
        await session_manager.add_participant(session_id, user_id)
        session = await session_manager.get_session(session_id)

    await websocket.accept()
    logger.info("WS connect user=%s session=%s", user_id, session_id)

    _local_connections.setdefault(session_id, {})[user_id] = websocket
    _ensure_subscriber(session_id)

    join_event = {"type": "join", "user_id": user_id, "session": session, "timestamp": _now()}
    await session_manager.publish_event(session_id, join_event)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "detail": "Invalid JSON"}))
                continue

            msg_type = msg.get("type")

            if msg_type in ("play", "pause"):
                position = float(msg.get("position", 0))
                state = "playing" if msg_type == "play" else "paused"
                await session_manager.update_playback(session_id, state, position)
                event = {
                    "type": msg_type, "user_id": user_id,
                    "position": position, "timestamp": _now(),
                }
                await session_manager.publish_event(session_id, event)

            elif msg_type == "seek":
                position = float(msg.get("position", 0))
                current = await session_manager.get_session(session_id)
                state = current["state"] if current else "paused"
                await session_manager.update_playback(session_id, state, position)
                event = {
                    "type": "seek", "user_id": user_id,
                    "position": position, "timestamp": _now(),
                }
                await session_manager.publish_event(session_id, event)

            elif msg_type == "chat":
                text = str(msg.get("text", "")).strip()
                if text:
                    chat_msg = await session_manager.add_chat_message(session_id, user_id, text)
                    event = {"type": "chat", **chat_msg}
                    await session_manager.publish_event(session_id, event)

            elif msg_type == "sync":
                # Reply privately to the requester only.
                current = await session_manager.get_session(session_id)
                await websocket.send_text(json.dumps({"type": "sync", "session": current}))

            else:
                await websocket.send_text(
                    json.dumps({"type": "error", "detail": f"Unknown message type: {msg_type}"})
                )

    except WebSocketDisconnect:
        logger.info("WS disconnect user=%s session=%s", user_id, session_id)
    except Exception:
        logger.exception("WS handler error user=%s session=%s", user_id, session_id)
    finally:
        # Drop the local socket but keep the user in the session participant set —
        # they remain a member (and can fetch chat history) even after disconnect.
        _local_connections.get(session_id, {}).pop(user_id, None)
        leave_event = {"type": "leave", "user_id": user_id, "timestamp": _now()}
        try:
            await session_manager.publish_event(session_id, leave_event)
        except Exception:
            logger.exception("Failed to publish leave event session=%s user=%s", session_id, user_id)
        await _stop_subscriber_if_idle(session_id)
