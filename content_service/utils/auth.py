from uuid import UUID

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.settings import get_settings

bearer = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> UUID:
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.auth.service_url}/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {credentials.credentials}"},
            timeout=5.0,
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    data = resp.json()
    return UUID(data["user_id"])


async def get_friend_ids(user_id: UUID, token: str) -> list[str]:
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.auth.service_url}/api/v1/users/friends/ids",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
    if resp.status_code != 200:
        return []
    return resp.json()
