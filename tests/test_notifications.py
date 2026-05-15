"""Notification-service: friend.request → RabbitMQ → worker → Redis → /notifications."""
import asyncio

import httpx


async def test_friend_request_creates_notification(
    http: httpx.AsyncClient, alice: dict, bob: dict
) -> None:
    r = await http.post(
        "/api/v1/users/friends/request",
        json={"addressee_id": bob["user_id"]},
        headers=alice["auth_header"],
    )
    assert r.status_code == 201

    # Worker is async — give it a moment to consume from RabbitMQ
    deadline = 10.0
    interval = 0.5
    notification = None
    while deadline > 0 and notification is None:
        await asyncio.sleep(interval)
        deadline -= interval
        r = await http.get("/api/v1/notifications", headers=bob["auth_header"])
        assert r.status_code == 200
        for item in r.json()["items"]:
            if item["kind"] == "friend.request" and item["payload"].get("requester_id") == alice["user_id"]:
                notification = item
                break

    assert notification is not None, "friend.request notification did not arrive"
    assert notification["read"] is False


async def test_mark_read(http: httpx.AsyncClient, bob: dict) -> None:
    r = await http.post("/api/v1/notifications/read", headers=bob["auth_header"])
    assert r.status_code == 204

    r = await http.get("/api/v1/notifications", headers=bob["auth_header"])
    assert r.status_code == 200
    assert r.json()["unread"] == 0
