"""initial schema: users + friendships

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
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            username VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS friendships (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            requester_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            addressee_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status VARCHAR(20) DEFAULT 'pending'
                CHECK (status IN ('pending','accepted','rejected')),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (requester_id, addressee_id)
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_friendships_requester ON friendships(requester_id);
        CREATE INDEX IF NOT EXISTS idx_friendships_addressee ON friendships(addressee_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS friendships;")
    op.execute("DROP TABLE IF EXISTS users;")
