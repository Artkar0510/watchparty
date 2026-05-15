from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from core.settings import get_settings

_client: AsyncIOMotorClient | None = None


async def init_mongo() -> None:
    global _client
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongo.url, serverSelectionTimeoutMS=5000)
    db = _client[settings.mongo.database]
    await db.likes.create_index([("user_id", 1), ("film_id", 1)], unique=True)
    await db.likes.create_index("film_id")
    await db.bookmarks.create_index([("user_id", 1), ("film_id", 1)], unique=True)
    await db.bookmarks.create_index("user_id")
    await db.reviews.create_index([("film_id", 1), ("created_at", -1)])
    await db.reviews.create_index([("user_id", 1), ("film_id", 1)], unique=True)


async def close_mongo() -> None:
    global _client
    if _client:
        _client.close()
        _client = None


def get_db() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("Mongo client is not initialized")
    settings = get_settings()
    return _client[settings.mongo.database]
