from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SessionCreate(BaseModel):
    film_id: str
    invited_user_ids: list[str] = []


class SessionOut(BaseModel):
    session_id: str
    film_id: str
    host_id: str
    state: Literal["playing", "paused"]
    position: float
    participants: list[str]
    created_at: datetime


class ChatMessage(BaseModel):
    user_id: str
    text: str
    timestamp: datetime
