from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from db.mongo import get_db
from schemas.ugc import ReviewCreate, ReviewOut
from services import notifier
from utils.auth import get_current_user_id

router = APIRouter()


def _serialize(doc: dict) -> ReviewOut:
    return ReviewOut(
        id=str(doc["_id"]),
        film_id=UUID(doc["film_id"]),
        user_id=UUID(doc["user_id"]),
        text=doc["text"],
        rating=doc.get("rating"),
        created_at=doc["created_at"],
    )


@router.post("/{film_id}", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
async def add_review(
    film_id: UUID,
    body: ReviewCreate,
    user_id: UUID = Depends(get_current_user_id),
):
    db = get_db()
    doc = {
        "user_id": str(user_id),
        "film_id": str(film_id),
        "text": body.text,
        "rating": body.rating,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        result = await db.reviews.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Review already exists for this film")
    doc["_id"] = result.inserted_id

    await notifier.publish(
        "review.created",
        {
            "event": "review.created",
            "user_id": str(user_id),
            "film_id": str(film_id),
            "rating": body.rating,
        },
    )
    return _serialize(doc)


@router.get("/film/{film_id}", response_model=list[ReviewOut])
async def film_reviews(film_id: UUID, limit: int = 50):
    db = get_db()
    cursor = db.reviews.find({"film_id": str(film_id)}).sort("created_at", -1).limit(limit)
    return [_serialize(doc) async for doc in cursor]


@router.delete("/{film_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_review(film_id: UUID, user_id: UUID = Depends(get_current_user_id)):
    db = get_db()
    result = await db.reviews.delete_one({"user_id": str(user_id), "film_id": str(film_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Review not found")
