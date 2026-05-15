"""Shared fixtures for integration tests.

Все тесты ходят через nginx (`BASE_URL`) — стек должен быть поднят через
`docker compose up`.
"""
import asyncio
import os
import uuid

import httpx
import pytest
import pytest_asyncio

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
WS_URL = os.getenv("WS_URL", "ws://localhost:8000")
HEALTH_TIMEOUT = 90  # seconds — ES + Postgres могут долго стартовать


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _wait_healthy(client: httpx.AsyncClient, path: str) -> None:
    deadline = HEALTH_TIMEOUT
    while deadline > 0:
        try:
            r = await client.get(path)
            if r.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        await asyncio.sleep(1)
        deadline -= 1
    raise RuntimeError(f"Service at {path} did not become healthy in {HEALTH_TIMEOUT}s")


@pytest_asyncio.fixture(scope="session")
async def http() -> httpx.AsyncClient:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        yield client


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _wait_for_stack(http: httpx.AsyncClient) -> None:
    """Wait for every service to report /health=200 before running tests."""
    for path in ("/health/auth", "/health/content", "/health/together",
                 "/health/ugc", "/health/notification"):
        await _wait_healthy(http, path)


async def _register_and_login(http: httpx.AsyncClient) -> dict:
    username = _unique("user")
    email = f"{username}@example.com"
    password = "Pa55word!"

    r = await http.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert r.status_code == 201, r.text
    user = r.json()

    r = await http.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    tokens = r.json()
    return {
        "user_id": user["id"],
        "username": username,
        "email": email,
        "password": password,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "auth_header": {"Authorization": f"Bearer {tokens['access_token']}"},
    }


@pytest_asyncio.fixture
async def alice(http: httpx.AsyncClient) -> dict:
    return await _register_and_login(http)


@pytest_asyncio.fixture
async def bob(http: httpx.AsyncClient) -> dict:
    return await _register_and_login(http)


@pytest_asyncio.fixture
async def friends(http: httpx.AsyncClient, alice: dict, bob: dict) -> tuple[dict, dict]:
    """Alice and Bob, with an accepted friendship between them."""
    r = await http.post(
        "/api/v1/users/friends/request",
        json={"addressee_id": bob["user_id"]},
        headers=alice["auth_header"],
    )
    assert r.status_code == 201, r.text
    friendship_id = r.json()["id"]

    r = await http.patch(
        f"/api/v1/users/friends/{friendship_id}/accept",
        headers=bob["auth_header"],
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "accepted"
    return alice, bob


@pytest_asyncio.fixture
async def film(http: httpx.AsyncClient) -> dict:
    """A unique film created via content-service."""
    title = _unique("Inception")
    r = await http.post(
        "/api/v1/films",
        json={
            "title": title,
            "description": "Test film",
            "rating": 8.5,
            "type": "movie",
            "genre_ids": [],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()
