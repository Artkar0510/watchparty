"""Together-service: create session + WebSocket play/pause/chat sync between two clients."""
import asyncio
import json
import os

import httpx
import pytest
import websockets

WS_URL = os.getenv("WS_URL", "ws://localhost:8000")


async def _recv_until(ws: websockets.WebSocketClientProtocol, msg_type: str,
                       timeout: float = 5.0) -> dict:
    """Receive messages until one matching msg_type arrives."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=deadline - asyncio.get_event_loop().time())
        except asyncio.TimeoutError:
            break
        msg = json.loads(raw)
        if msg.get("type") == msg_type:
            return msg
    raise AssertionError(f"Did not receive {msg_type} in {timeout}s")


async def test_create_session(http: httpx.AsyncClient, friends: tuple, film: dict) -> None:
    alice, bob = friends
    r = await http.post(
        "/api/v1/sessions",
        json={"film_id": film["id"], "invited_user_ids": [bob["user_id"]]},
        headers=alice["auth_header"],
    )
    assert r.status_code == 201
    session = r.json()
    assert session["film_id"] == film["id"]
    assert session["host_id"] == alice["user_id"]
    assert alice["user_id"] in session["participants"]
    assert bob["user_id"] in session["participants"]


async def test_websocket_play_pause_chat(http: httpx.AsyncClient, friends: tuple, film: dict) -> None:
    alice, bob = friends
    r = await http.post(
        "/api/v1/sessions",
        json={"film_id": film["id"], "invited_user_ids": [bob["user_id"]]},
        headers=alice["auth_header"],
    )
    session_id = r.json()["session_id"]

    alice_ws_url = f"{WS_URL}/ws/{session_id}?token={alice['access_token']}"
    bob_ws_url = f"{WS_URL}/ws/{session_id}?token={bob['access_token']}"

    async with websockets.connect(alice_ws_url) as alice_ws, \
               websockets.connect(bob_ws_url) as bob_ws:

        # Both should see each other's join (via Redis fan-out, possibly async)
        await asyncio.sleep(0.5)

        # Drain any pending messages so the assertions below see fresh events
        async def drain(ws):
            try:
                while True:
                    await asyncio.wait_for(ws.recv(), timeout=0.2)
            except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                pass
        await asyncio.gather(drain(alice_ws), drain(bob_ws))

        # Alice plays at position 10 → Bob receives
        await alice_ws.send(json.dumps({"type": "play", "position": 10.0}))
        play = await _recv_until(bob_ws, "play")
        assert play["user_id"] == alice["user_id"]
        assert play["position"] == 10.0

        # Bob pauses at 25 → Alice receives
        await bob_ws.send(json.dumps({"type": "pause", "position": 25.0}))
        pause = await _recv_until(alice_ws, "pause")
        assert pause["user_id"] == bob["user_id"]
        assert pause["position"] == 25.0

        # Alice chats → Bob receives
        await alice_ws.send(json.dumps({"type": "chat", "text": "Привет!"}))
        chat = await _recv_until(bob_ws, "chat")
        assert chat["text"] == "Привет!"
        assert chat["user_id"] == alice["user_id"]

    # After both disconnected, chat history is in Redis
    r = await http.get(f"/api/v1/sessions/{session_id}/chat", headers=alice["auth_header"])
    assert r.status_code == 200
    history = r.json()
    assert any(m["text"] == "Привет!" for m in history)
