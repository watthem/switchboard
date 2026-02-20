"""Minimal Herald application.

Mounts the v1 governance router and serves the dashboard.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse

from herald.v1.routes import router as v1_router

_ROOT = Path(__file__).resolve().parent.parent
_DASHBOARD = _ROOT / "dashboard" / "index.html"
_SHARED_CSS = _ROOT / "docs" / "shared.css"


def create_app() -> FastAPI:
    app = FastAPI(title="Herald", version="2026.2.19-POC")
    app.include_router(v1_router)

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard():
        return _DASHBOARD.read_text(encoding="utf-8")

    @app.get("/docs/shared.css")
    async def shared_css():
        return FileResponse(_SHARED_CSS, media_type="text/css")

    return app


app = create_app()
