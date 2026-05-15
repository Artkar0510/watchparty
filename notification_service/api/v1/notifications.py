from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from services import store
from utils.auth import get_current_user_id

router = APIRouter()


@router.get("")
async def list_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    user_id: UUID = Depends(get_current_user_id),
):
    items = await store.list_for(str(user_id), limit=limit)
    unread = await store.unread_count(str(user_id))
    return {"items": items, "unread": unread}


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(user_id: UUID = Depends(get_current_user_id)):
    await store.mark_all_read(str(user_id))
