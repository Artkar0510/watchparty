from fastapi import APIRouter
from api.v1.sessions import router as sessions_router

v1_router = APIRouter()
v1_router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
