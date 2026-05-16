from fastapi import APIRouter, Depends, HTTPException

from schemas.session import SessionCreate, SessionOut
from services import notifier, session_manager
from services.auth_client import authenticate

router = APIRouter()


@router.post("", response_model=SessionOut, status_code=201)
async def create_session(
    body: SessionCreate,
    user_id: str = Depends(authenticate),
):
    session = await session_manager.create_session(
        film_id=body.film_id,
        host_id=user_id,
        invited=body.invited_user_ids,
    )
    await notifier.publish(
        "session.created",
        {
            "event": "session.created",
            "session_id": session["session_id"],
            "film_id": session["film_id"],
            "host_id": session["host_id"],
            "invited_user_ids": body.invited_user_ids,
        },
    )
    return session


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: str, user_id: str = Depends(authenticate)):
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if user_id not in session["participants"]:
        raise HTTPException(status_code=403, detail="Not a participant")
    return session


@router.get("/{session_id}/chat")
async def get_chat(session_id: str, user_id: str = Depends(authenticate)):
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if user_id not in session["participants"]:
        raise HTTPException(status_code=403, detail="Not a participant")
    return await session_manager.get_chat_history(session_id)
