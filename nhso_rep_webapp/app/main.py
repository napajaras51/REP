"""FastAPI application factory for the NHSO REP web application."""

from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .api import auth, downloads, pages


def create_app() -> FastAPI:
    """Create the local NHSO REP FastAPI application."""
    application = FastAPI(
        title="NHSO REP Download Manager",
        version="0.2.0",
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )

    @application.middleware("http")
    async def reject_cross_origin_writes(request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and urlparse(origin).hostname not in {"127.0.0.1", "localhost", "::1"}:
                return JSONResponse(status_code=403, content={"detail": "Cross-origin request blocked"})
        return await call_next(request)

    static_dir = Path(__file__).resolve().parent / "static"
    application.mount("/static", StaticFiles(directory=static_dir), name="static")
    application.include_router(pages.router)
    application.include_router(auth.router)
    application.include_router(downloads.router)

    @application.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
