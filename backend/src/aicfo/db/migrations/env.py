from __future__ import annotations

from alembic import context
from sqlalchemy import Connection

from aicfo.config import get_settings
from aicfo.db.models import Base
from aicfo.db.session import make_engine


# Run migrations on a connection, comparing against our models.
def run(connection: Connection) -> None:
    # Tell Alembic which tables the models define.
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    # Everything inside one transaction.
    with context.begin_transaction():
        # Apply the pending scripts.
        context.run_migrations()


# A connection handed in by migrate.py (tests, CLI), if any.
connection = context.config.attributes.get("connection")
# Use the supplied connection.
if connection is not None:
    # Migrate on it.
    run(connection)
# Alembic's own command line: connect from settings.
else:
    # The database URL.
    url = context.config.get_main_option("sqlalchemy.url") or get_settings().database_url
    # Connect.
    with make_engine(url).connect() as conn:
        # Migrate.
        run(conn)
