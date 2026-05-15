from uuid import UUID
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
    state: str
    position: float
    participants: list[str]
    created_at: str


class WsMessage(BaseModel):
    type: Literal["play", "pause", "seek", "chat", "join", "leave", "sync"]
    position: float | None = None
    text: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    timestamp: str | None = None


class ChatMessage(BaseModel):
    user_id: str
    text: str
    timestamp: str
