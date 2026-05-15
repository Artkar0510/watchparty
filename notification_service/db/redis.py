from redis.asyncio import Redis

from core.settings import get_settings

_client: Redis | None = None


async def init_redis() -> None:
    global _client
    settings = get_settings()
    _client = Redis.from_url(settings.redis.url, decode_responses=True)


async def close_redis() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None


def get_redis() -> Redis:
    if _client is None:
        raise RuntimeError("Redis client is not initialized")
    return _client
