from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
# Also add the project root so absolute package imports work in IDEs
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# this is the Alembic Config object, which provides access to values within the .ini file
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Try both local-module and package-style imports so it works in CLI and IDE
try:
    from db import DATABASE_URL, Base  # running from services/grading
except Exception:
    from services.grading.db import DATABASE_URL, Base  # running from project root / IDE

# Ensure models are imported so tables are registered on Base.metadata during autogenerate
try:
    import models as _models  # when running from grading project root (CWD)
except Exception as e1:
    try:
        from services.grading import models as _models  # when running from monorepo root / IDE
    except Exception as e2:
        raise RuntimeError(
            "Alembic could not import the models module. "
            "Make sure you run Alembic from the grading project, or that PYTHONPATH includes it."
        ) from e2

target_metadata = Base.metadata

# Safety check: ensure key tables are registered in metadata; otherwise autogenerate may emit destructive diffs
if "attempts" not in target_metadata.tables:
    raise RuntimeError(
        "Alembic autogenerate safety: 'attempts' is not present in Base.metadata. "
        "Ensure models are imported and that Attempt.__tablename__ = 'attempts'."
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,  # detect column type changes
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode'."""
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
