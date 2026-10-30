from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aicfo.config import get_settings


# Hosted Postgres gives out postgres://…; make it use the psycopg 3 driver.
def normalise_url(url: str) -> str:
    """Hosted Postgres (Supabase, Neon, Render) hands out `postgres://`; use the psycopg 3 driver."""
    # Known older spellings.
    for prefix in ("postgres://", "postgresql://", "postgresql+asyncpg://"):
        # Matched.
        if url.startswith(prefix):
            # Rewrite the scheme only.
            return "postgresql+psycopg://" + url[len(prefix) :]
    # Anything else is left alone (e.g. sqlite).
    return url


# Create the database connection pool.
def make_engine(url: str) -> Engine:
    # Fix the scheme first.
    url = normalise_url(url)
    # SQLite (tests and the container smoke test).
    if url.startswith("sqlite"):
        # Tests: one shared in-memory connection, usable from FastAPI's worker threads.
        # Allow use from FastAPI's worker threads.
        kw: dict[str, object] = {"connect_args": {"check_same_thread": False}}
        # An in-memory database needs one shared connection or it would be empty per connection.
        if ":memory:" in url or url == "sqlite://":
            # Share a single connection.
            kw["poolclass"] = StaticPool
        # SQLite engine.
        return create_engine(url, **kw)
    # Postgres: check connections before use, small pool.
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


# One engine per process.
@lru_cache
# The shared engine, built from settings.
def get_engine() -> Engine:
    # Create it on first use.
    return make_engine(get_settings().database_url)


# One session factory per process.
@lru_cache
# Session factory bound to the engine.
def _factory() -> sessionmaker[Session]:
    # expire_on_commit=False keeps objects usable after the request commits.
    return sessionmaker(get_engine(), expire_on_commit=False)


# FastAPI dependency: one database transaction per request.
def get_session() -> Iterator[Session]:
    """FastAPI dependency: one transaction per request, committed on success."""
    # Commit if the request succeeds, roll back if it raises.
    with _factory().begin() as session:
        # Hand the session to the route.
        yield session
