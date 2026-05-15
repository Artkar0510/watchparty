from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.security import decode_token
from db.postgres import get_pool
from schemas.user import FriendRequest, FriendshipOut, UserOut

router = APIRouter()
bearer = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> UUID:
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token")
    return UUID(payload["sub"])


@router.get("/me", response_model=UserOut)
async def get_me(user_id: UUID = Depends(get_current_user_id)):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, email, is_active, created_at FROM users WHERE id=$1",
            user_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: UUID):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, email, is_active, created_at FROM users WHERE id=$1",
            user_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)


@router.post("/friends/request", response_model=FriendshipOut, status_code=status.HTTP_201_CREATED)
async def send_friend_request(
    body: FriendRequest,
    user_id: UUID = Depends(get_current_user_id),
):
    if user_id == body.addressee_id:
        raise HTTPException(status_code=400, detail="Cannot friend yourself")

    pool = get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id, status FROM friendships WHERE requester_id=$1 AND addressee_id=$2",
            user_id, body.addressee_id,
        )
        if existing:
            raise HTTPException(status_code=400, detail=f"Request already exists: {existing['status']}")

        row = await conn.fetchrow(
            """INSERT INTO friendships (requester_id, addressee_id)
               VALUES ($1, $2) RETURNING id, requester_id, addressee_id, status, created_at""",
            user_id, body.addressee_id,
        )
    return dict(row)


@router.patch("/friends/{friendship_id}/accept", response_model=FriendshipOut)
async def accept_friend_request(
    friendship_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE friendships SET status='accepted'
               WHERE id=$1 AND addressee_id=$2 AND status='pending'
               RETURNING id, requester_id, addressee_id, status, created_at""",
            friendship_id, user_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Friendship request not found")
    return dict(row)


@router.get("/friends/list", response_model=list[UserOut])
async def get_friends(user_id: UUID = Depends(get_current_user_id)):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT u.id, u.username, u.email, u.is_active, u.created_at
               FROM users u
               JOIN friendships f ON (
                   (f.requester_id=$1 AND f.addressee_id=u.id) OR
                   (f.addressee_id=$1 AND f.requester_id=u.id)
               )
               WHERE f.status='accepted'""",
            user_id,
        )
    return [dict(r) for r in rows]


@router.get("/friends/ids", response_model=list[str])
async def get_friend_ids(user_id: UUID = Depends(get_current_user_id)):
    """Internal: returns friend UUIDs as strings for inter-service calls."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT CASE
                   WHEN f.requester_id=$1 THEN f.addressee_id
                   ELSE f.requester_id
               END AS friend_id
               FROM friendships f
               WHERE (f.requester_id=$1 OR f.addressee_id=$1) AND f.status='accepted'""",
            user_id,
        )
    return [str(r["friend_id"]) for r in rows]
