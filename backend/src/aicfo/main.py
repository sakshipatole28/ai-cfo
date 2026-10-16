from __future__ import annotations

from fastapi import FastAPI

from aicfo import __version__
from aicfo.config import get_settings
from aicfo.security import redaction


def create_app() -> FastAPI:
    redaction.install()
    app = FastAPI(title="AI CFO API", version=__version__)

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__, "env": get_settings().env}

    return app


app = create_app()
