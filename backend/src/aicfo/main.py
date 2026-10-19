from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aicfo import __version__
from aicfo.api import agents, connections, rag
from aicfo.config import get_settings
from aicfo.security import redaction


def create_app() -> FastAPI:
    redaction.install()
    settings = get_settings()
    app = FastAPI(title="AI CFO API", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__, "env": settings.env}

    app.include_router(rag.router)
    app.include_router(agents.router)
    app.include_router(connections.router)
    return app


app = create_app()
