"""Alembic env: builds DB URL from Pydantic Settings (env vars), runs sync migrations."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from core.settings import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
pg = settings.postgresql
sync_url = f"postgresql+psycopg2://{pg.user}:{pg.password}@{pg.host}:{pg.port}/{pg.database}"
config.set_main_option("sqlalchemy.url", sync_url)

target_metadata = None  # raw-SQL migrations


def run_migrations_offline() -> None:
    context.configure(
        url=sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
