"""Start the NHSO REP web application on the local machine only."""

import uvicorn


HOST = "127.0.0.1"
PORT = 8000


def main() -> None:
    """Run Uvicorn with a localhost-only binding."""
    uvicorn.run(
        "nhso_rep_webapp.app.main:app",
        host=HOST,
        port=PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()

