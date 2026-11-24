"""FastAPI application. Entry point: `uvicorn jobfinder.web.app:app`."""

from fastapi import FastAPI

from jobfinder import __version__

app = FastAPI(title="Job Finder", version=__version__, docs_url=None, redoc_url=None)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness check for the hosting platform. Carries no data."""
    return {"status": "ok", "version": __version__}
