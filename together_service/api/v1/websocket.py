"""
WebSocket endpoint for real-time watch synchronization.

Architecture: every event flows through Redis pub/sub. Each running instance of
together-service subscribes to a per-session channel and forwards messages to
its locally-connected WebSocket clients only. This makes the service horizontally
scalable — clients in session X may be split across multiple instances.

Auth: token is delivered as the FIRST message after the socket is accepted,
not as a query string. Putting JWTs in URLs leaks them into nginx/uvicorn
access logs, browser history and Referer headers.

Wire protocol (JSON messages):
  Client → Server:
    {"type": "auth",  "token": "<jwt>"}    — REQUIRED first message
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

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.utils import utc_now
from db.redis import get_redis
from services import session_manager
from services.auth_client import verify_token

logger = logging.getLogger(__name__)
router = APIRouter()

# Local connections only — each instance tracks its own clients.
# session_id -> {user_id -> WebSocket}
_local_connections: dict[str, dict[str, WebSocket]] = {}
# session_id -> asyncio.Task running the Redis subscriber
_subscribers: dict[str, asyncio.Task] = {}

# How long we wait for the client to send the auth frame after connecting.
AUTH_TIMEOUT_SECONDS = 10.0


def _channel(session_id: str) -> str:
    return f"session:{session_id}:events"


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


async def _safe_close(websocket: WebSocket, code: int, reason: str) -> None:
    """Close the WS but swallow errors if peer already disconnected.

    Without this, ``await websocket.close()`` after a remote-side disconnect
    raises RuntimeError("Unexpected ASGI message 'websocket.close', after
    sending 'websocket.close' or response already completed.") and Sentry/logs
    fill up with noise.
    """
    try:
        await websocket.close(code=code, reason=reason)
    except Exception as exc:
        logger.debug("Suppressed close() error (peer likely already gone): %s", exc)


async def _read_auth_frame(websocket: WebSocket) -> tuple[str | None, bool]:
    """Read the first frame; expect ``{"type": "auth", "token": "..."}``.

    Returns ``(token_or_None, peer_disconnected)``. When ``peer_disconnected``
    is True, the caller must not call ``websocket.close()``.
    """
    try:
        raw = await asyncio.wait_for(
            websocket.receive_text(), timeout=AUTH_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        return None, False
    except WebSocketDisconnect:
        return None, True
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        return None, False
    if msg.get("type") != "auth":
        return None, False
    token = msg.get("token")
    if isinstance(token, str) and token:
        return token, False
    return None, False


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    # Accept first so we can read the auth frame; reject afterwards if invalid.
    await websocket.accept()

    token, peer_gone = await _read_auth_frame(websocket)
    if peer_gone:
        return
    http_client = websocket.app.state.http_client
    user_id = await verify_token(token or "", http_client)
    if not user_id:
        await _safe_close(websocket, code=4001, reason="Unauthorized")
        return

    session = await session_manager.get_session(session_id)
    if not session:
        await _safe_close(websocket, code=4004, reason="Session not found")
        return

    if user_id not in session["participants"]:
        await session_manager.add_participant(session_id, user_id)
        session = await session_manager.get_session(session_id)

    logger.info("WS connect user=%s session=%s", user_id, session_id)

    _local_connections.setdefault(session_id, {})[user_id] = websocket
    _ensure_subscriber(session_id)

    join_event = {"type": "join", "user_id": user_id, "session": session, "timestamp": utc_now()}
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
                    "position": position, "timestamp": utc_now(),
                }
                await session_manager.publish_event(session_id, event)

            elif msg_type == "seek":
                position = float(msg.get("position", 0))
                current = await session_manager.get_session(session_id)
                state = current["state"] if current else "paused"
                await session_manager.update_playback(session_id, state, position)
                event = {
                    "type": "seek", "user_id": user_id,
                    "position": position, "timestamp": utc_now(),
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
        leave_event = {"type": "leave", "user_id": user_id, "timestamp": utc_now()}
        try:
            await session_manager.publish_event(session_id, leave_event)
        except Exception:
            logger.exception("Failed to publish leave event session=%s user=%s", session_id, user_id)
        await _stop_subscriber_if_idle(session_id)
