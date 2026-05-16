"""Shared client for the auth service token verification.

Both REST endpoints and the WebSocket handler need to validate JWTs against
auth-service. Previously both spots constructed their own ``httpx.AsyncClient``
on every request — that's a fresh TCP connection per call, no pool, no
keep-alive. We now keep a single client for the whole app lifetime (created in
``main.lifespan``) and reuse it here.
"""
from __future__ import annotations

import logging

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.settings import get_settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer()


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Dependency: return the shared httpx client stored in app.state."""
    client = getattr(request.app.state, "http_client", None)
    if client is None:
        # Should never happen if lifespan ran; raise loudly if it did.
        raise RuntimeError("HTTP client is not initialized — check lifespan")
    return client


async def verify_token(token: str, client: httpx.AsyncClient) -> str | None:
    """Ask auth-service whether ``token`` is valid; return user_id or None."""
    if not token:
        return None
    settings = get_settings()
    try:
        resp = await client.get(
            f"{settings.auth.service_url}/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("Token verification request failed: %s", exc)
        return None
    if resp.status_code != 200:
        return None
    return resp.json().get("user_id")


async def authenticate(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    client: httpx.AsyncClient = Depends(get_http_client),
) -> str:
    """FastAPI dependency for REST endpoints: returns user_id or raises 401."""
    user_id = await verify_token(credentials.credentials, client)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id
