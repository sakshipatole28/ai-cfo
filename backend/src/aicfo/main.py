from __future__ import annotations

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from aicfo import __version__
from aicfo.api import agents, auth, connections, rag, workspace
from aicfo.config import get_settings
from aicfo.security import redaction


# Build the FastAPI application (a function so tests can create fresh ones).
def create_app() -> FastAPI:
    # Mask PAN, phones, emails and tokens in every log line.
    redaction.install()
    # Configuration from environment / .env.
    settings = get_settings()
    # The app object; its docs are at /docs.
    app = FastAPI(title="AI CFO API", version=__version__)
    # CORS: only the configured console origins may call the API from a browser.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # GET /: a friendly landing answer, so opening the API's address in a browser is not a 404.
    @app.get("/", include_in_schema=False)
    # Points to the interactive docs and the health check.
    def root() -> dict[str, str]:
        # Name, status and where to go next.
        return {"service": "AI CFO API", "status": "ok", "docs": "/docs", "health": "/health"}

    # GET /favicon.ico: browsers ask for it automatically; answer "no content" instead of a 404.
    @app.get("/favicon.ico", include_in_schema=False)
    # Empty reply.
    def favicon() -> Response:
        # 204 means "nothing here, and that is fine".
        return Response(status_code=204)

    # GET /health: used by Docker, Render and CI to know the API is up.
    @app.get("/health", tags=["ops"])
    # Cheap check; touches no database.
    def health() -> dict[str, str]:
        # Status, version and environment.
        return {"status": "ok", "version": __version__, "env": settings.env}

    # Rulebook search and cited answers.
    app.include_router(rag.router)
    # Clients, reviews and the Copilot.
    app.include_router(agents.router)
    # Read-only broker connections (Dhan).
    app.include_router(connections.router)
    # Pipeline, persisted reviews, approvals, audit.
    app.include_router(workspace.router)
    # Firm accounts, sign-in and team access.
    app.include_router(auth.router)
    # The configured application.
    return app


# The instance uvicorn serves: `uvicorn aicfo.main:app`.
app = create_app()
