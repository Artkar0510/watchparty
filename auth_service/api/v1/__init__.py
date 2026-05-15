from fastapi import APIRouter
from api.v1.auth import router as auth_router
from api.v1.users import router as users_router

v1_router = APIRouter()
v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
v1_router.include_router(users_router, prefix="/users", tags=["users"])
