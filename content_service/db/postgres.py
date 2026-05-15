import asyncpg

from core.settings import get_settings

_pool: asyncpg.Pool | None = None


async def init_db() -> None:
    global _pool
    settings = get_settings()
    _pool = await asyncpg.create_pool(dsn=settings.postgresql.dsn, min_size=2, max_size=10)


async def close_db() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    return _pool
