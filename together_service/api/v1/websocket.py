"""
WebSocket endpoint for real-time watch synchronization.

Protocol (JSON messages):
  Client → Server:
    {"type": "join"}                              — join/rejoin session
    {"type": "play", "position": 12.5}            — start playback at position
    {"type": "pause", "position": 12.5}           — pause at position
    {"type": "seek", "position": 60.0}            — seek to position
    {"type": "chat", "text": "Hello!"}            — send chat message
    {"type": "sync"}                              — request current state

  Server → Client (broadcast):
    {"type": "join",   "user_id": "...", "session": {...}}
    {"type": "play",   "user_id": "...", "position": 12.5}
    {"type": "pause",  "user_id": "...", "position": 12.5}
    {"type": "seek",   "user_id": "...", "position": 60.0}
    {"type": "chat",   "user_id": "...", "text": "...", "timestamp": "..."}
    {"type": "leave",  "user_id": "..."}
    {"type": "sync",   "session": {...}}
    {"type": "error",  "detail": "..."}
"""
import asyncio
import json
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.settings import get_settings
from db.redis import get_redis
from services import session_manager

router = APIRouter()

# active_connections: session_id → {user_id → WebSocket}
active_connections: dict[str, dict[str, WebSocket]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    except Exception:
        pass
    return None


async def broadcast(session_id: str, message: dict, exclude_user: str | None = None) -> None:
    connections = active_connections.get(session_id, {})
    payload = json.dumps(message)
    dead = []
    for uid, ws in connections.items():
        if uid == exclude_user:
            continue
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(uid)
    for uid in dead:
        connections.pop(uid, None)


async def subscribe_redis_events(session_id: str) -> None:
    """Subscribe to Redis pub/sub and broadcast events to WebSocket clients."""
    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"session:{session_id}:events")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                event = json.loads(message["data"])
                await broadcast(session_id, event)
    except Exception:
        pass
    finally:
        await pubsub.unsubscribe(f"session:{session_id}:events")
        await pubsub.aclose()


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

    await websocket.accept()

    if session_id not in active_connections:
        active_connections[session_id] = {}
        asyncio.create_task(subscribe_redis_events(session_id))

    active_connections[session_id][user_id] = websocket

    join_event = {"type": "join", "user_id": user_id, "session": session, "timestamp": _now()}
    await broadcast(session_id, join_event)

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
                event = {"type": msg_type, "user_id": user_id, "position": position, "timestamp": _now()}
                await session_manager.publish_event(session_id, event)

            elif msg_type == "seek":
                position = float(msg.get("position", 0))
                session_data = await session_manager.get_session(session_id)
                current_state = session_data["state"] if session_data else "paused"
                await session_manager.update_playback(session_id, current_state, position)
                event = {"type": "seek", "user_id": user_id, "position": position, "timestamp": _now()}
                await session_manager.publish_event(session_id, event)

            elif msg_type == "chat":
                text = str(msg.get("text", "")).strip()
                if text:
                    chat_msg = await session_manager.add_chat_message(session_id, user_id, text)
                    event = {"type": "chat", "user_id": user_id, **chat_msg}
                    await session_manager.publish_event(session_id, event)

            elif msg_type == "sync":
                current = await session_manager.get_session(session_id)
                await websocket.send_text(json.dumps({"type": "sync", "session": current}))

    except WebSocketDisconnect:
        pass
    finally:
        active_connections.get(session_id, {}).pop(user_id, None)
        await session_manager.remove_participant(session_id, user_id)
        leave_event = {"type": "leave", "user_id": user_id, "timestamp": _now()}
        await broadcast(session_id, leave_event)
