from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from db.mongo import get_db
from schemas.ugc import BookmarkCreate, BookmarkOut
from utils.auth import get_current_user_id

router = APIRouter()


@router.post("", response_model=BookmarkOut, status_code=status.HTTP_201_CREATED)
async def add_bookmark(body: BookmarkCreate, user_id: UUID = Depends(get_current_user_id)):
    db = get_db()
    doc = {
        "user_id": str(user_id),
        "film_id": str(body.film_id),
        "created_at": datetime.now(timezone.utc),
    }
    try:
        await db.bookmarks.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Already bookmarked")
    return BookmarkOut(film_id=body.film_id, user_id=user_id, created_at=doc["created_at"])


@router.get("", response_model=list[BookmarkOut])
async def list_bookmarks(user_id: UUID = Depends(get_current_user_id)):
    db = get_db()
    cursor = db.bookmarks.find({"user_id": str(user_id)}).sort("created_at", -1)
    return [
        BookmarkOut(
            film_id=UUID(doc["film_id"]),
            user_id=UUID(doc["user_id"]),
            created_at=doc["created_at"],
        )
        async for doc in cursor
    ]


@router.delete("/{film_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_bookmark(film_id: UUID, user_id: UUID = Depends(get_current_user_id)):
    db = get_db()
    result = await db.bookmarks.delete_one({"user_id": str(user_id), "film_id": str(film_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Bookmark not found")
