from fastapi import APIRouter
from api.v1.films import router as films_router
from api.v1.genres import router as genres_router
from api.v1.watchlist import router as watchlist_router
from api.v1.matches import router as matches_router

v1_router = APIRouter()
v1_router.include_router(films_router, prefix="/films", tags=["films"])
v1_router.include_router(genres_router, prefix="/genres", tags=["genres"])
v1_router.include_router(watchlist_router, prefix="/watchlist", tags=["watchlist"])
v1_router.include_router(matches_router, prefix="/matches", tags=["matches"])
