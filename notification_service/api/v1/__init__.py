from fastapi import APIRouter

from api.v1.notifications import router as notifications_router

v1_router = APIRouter()
v1_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
