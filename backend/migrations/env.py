"""
migrations/env.py
=================
Point d'entrée Alembic : relie les migrations aux modèles SQLAlchemy.

L'URL de la base vient de DATABASE_URL (.env), sauf surcharge explicite via
`alembic -x db_url=...` (utile pour tester les migrations sur une base jetable).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.database.models import Base  # importe aussi les modèles dans Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    override = context.get_x_argument(as_dictionary=True).get("db_url")
    if override:
        return override

    from config import get_settings
    return get_settings().database_url


def run_migrations_offline() -> None:
    """Génère le SQL sans connexion (alembic upgrade --sql)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Applique les migrations sur la base."""
    connectable = engine_from_config(
        {"sqlalchemy.url": _database_url()},
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
