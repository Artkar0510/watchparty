from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from db.mongo import get_db
from schemas.ugc import LikeOut, LikeStats
from services import notifier
from utils.auth import get_current_user_id

router = APIRouter()


@router.post("/{film_id}", response_model=LikeOut, status_code=status.HTTP_201_CREATED)
async def add_like(film_id: UUID, user_id: UUID = Depends(get_current_user_id)):
    db = get_db()
    doc = {
        "user_id": str(user_id),
        "film_id": str(film_id),
        "created_at": datetime.now(timezone.utc),
    }
    try:
        await db.likes.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Already liked")

    await notifier.publish(
        "like.created",
        {"event": "like.created", "user_id": str(user_id), "film_id": str(film_id)},
    )
    return LikeOut(film_id=film_id, user_id=user_id, created_at=doc["created_at"])


@router.delete("/{film_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_like(film_id: UUID, user_id: UUID = Depends(get_current_user_id)):
    db = get_db()
    result = await db.likes.delete_one({"user_id": str(user_id), "film_id": str(film_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Like not found")


@router.get("/film/{film_id}", response_model=LikeStats)
async def film_likes(film_id: UUID):
    db = get_db()
    count = await db.likes.count_documents({"film_id": str(film_id)})
    return LikeStats(film_id=film_id, likes_count=count)


@router.get("/me", response_model=list[LikeOut])
async def my_likes(user_id: UUID = Depends(get_current_user_id)):
    db = get_db()
    cursor = db.likes.find({"user_id": str(user_id)}).sort("created_at", -1)
    return [
        LikeOut(
            film_id=UUID(doc["film_id"]),
            user_id=UUID(doc["user_id"]),
            created_at=doc["created_at"],
        )
        async for doc in cursor
    ]
