"""Run Alembic migrations from code (CLI, container start-up, tests)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

# Folder holding the Alembic scripts (shipped inside the package).
MIGRATIONS = Path(__file__).parent / "migrations"


# Run an Alembic command on an existing engine.
def _run(engine: Engine, fn: str, revision: str) -> None:
    # Alembic configuration.
    cfg = Config()
    # Where the migration scripts live.
    cfg.set_main_option("script_location", str(MIGRATIONS))
    # One transaction; if a migration fails nothing is half-applied.
    with engine.begin() as conn:
        # Hand the open connection to env.py.
        cfg.attributes["connection"] = conn
        # command.upgrade or command.downgrade.
        getattr(command, fn)(cfg, revision)


# Bring the database to `revision` (default: latest).
def upgrade(engine: Engine, revision: str = "head") -> None:
    # Apply migrations.
    _run(engine, "upgrade", revision)


# Roll back to `revision` (default: empty).
def downgrade(engine: Engine, revision: str = "base") -> None:
    # Revert migrations.
    _run(engine, "downgrade", revision)
