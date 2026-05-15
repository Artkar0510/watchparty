import asyncpg

from core.settings import get_settings

_pool: asyncpg.Pool | None = None


async def init_db() -> None:
    global _pool
    settings = get_settings()
    _pool = await asyncpg.create_pool(dsn=settings.postgresql.dsn, min_size=2, max_size=10)
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS friendships (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                requester_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                addressee_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending','accepted','rejected')),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (requester_id, addressee_id)
            );
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
