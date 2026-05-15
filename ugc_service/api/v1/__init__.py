from fastapi import APIRouter

from api.v1.likes import router as likes_router
from api.v1.bookmarks import router as bookmarks_router
from api.v1.reviews import router as reviews_router

v1_router = APIRouter()
v1_router.include_router(likes_router, prefix="/likes", tags=["likes"])
v1_router.include_router(bookmarks_router, prefix="/bookmarks", tags=["bookmarks"])
v1_router.include_router(reviews_router, prefix="/reviews", tags=["reviews"])
