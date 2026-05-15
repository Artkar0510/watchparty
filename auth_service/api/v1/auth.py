from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from core.settings import get_settings
from db.postgres import get_pool
from db.redis import get_redis
from schemas.user import RefreshRequest, TokenPair, UserLogin, UserRegister, UserOut

router = APIRouter()
bearer = HTTPBearer()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: UserRegister):
    pool = get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM users WHERE email=$1 OR username=$2",
            body.email, body.username,
        )
        if existing:
            raise HTTPException(status_code=400, detail="Email or username already taken")

        row = await conn.fetchrow(
            """INSERT INTO users (username, email, password_hash)
               VALUES ($1, $2, $3) RETURNING id, username, email, is_active, created_at""",
            body.username, body.email, hash_password(body.password),
        )
    return dict(row)


@router.post("/login", response_model=TokenPair)
async def login(body: UserLogin):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, password_hash, is_active FROM users WHERE email=$1", body.email
        )
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not row["is_active"]:
        raise HTTPException(status_code=403, detail="Account is inactive")

    user_id: UUID = row["id"]
    access = create_access_token(user_id)
    refresh = create_refresh_token(user_id)

    redis = get_redis()
    settings = get_settings()
    await redis.setex(
        f"refresh:{str(user_id)}",
        settings.app.refresh_token_expire_days * 86400,
        refresh,
    )
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)
async def refresh_tokens(body: RefreshRequest):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload["sub"]
    redis = get_redis()
    stored = await redis.get(f"refresh:{user_id}")
    if stored != body.refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token revoked")

    new_access = create_access_token(UUID(user_id))
    new_refresh = create_refresh_token(UUID(user_id))

    settings = get_settings()
    await redis.setex(
        f"refresh:{user_id}",
        settings.app.refresh_token_expire_days * 86400,
        new_refresh,
    )
    return TokenPair(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    redis = get_redis()
    await redis.delete(f"refresh:{payload['sub']}")


@router.get("/verify")
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    """Internal endpoint used by other services to validate tokens."""
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"user_id": payload["sub"]}
