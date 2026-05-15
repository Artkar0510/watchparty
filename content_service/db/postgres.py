import asyncpg

from core.settings import get_settings

_pool: asyncpg.Pool | None = None


async def init_db() -> None:
    global _pool
    settings = get_settings()
    _pool = await asyncpg.create_pool(dsn=settings.postgresql.dsn, min_size=2, max_size=10)
    async with _pool.acquire() as conn:
        # genre, film_work, genre_film_work are created by Django admin migrations.
        # We only create watchlist here (not managed by Django).
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL,
                film_work_id UUID NOT NULL REFERENCES film_work(id) ON DELETE CASCADE,
                added_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (user_id, film_work_id)
            );

            CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist(user_id);
        """)


async def close_db() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    return _pool
