"""FastAPI application factory for the NHSO REP web application."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create the local NHSO REP FastAPI application."""
    application = FastAPI(
        title="NHSO REP Download Manager",
        version="0.1.0",
    )

    @application.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()

