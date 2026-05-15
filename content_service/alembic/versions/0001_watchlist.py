"""initial schema: watchlist (film_work, genre, genre_film_work are owned by Django)

Revision ID: 0001
Revises:
Create Date: 2026-05-15
"""
from alembic import op


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            film_work_id UUID NOT NULL REFERENCES film_work(id) ON DELETE CASCADE,
            added_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (user_id, film_work_id)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist(user_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS watchlist;")
