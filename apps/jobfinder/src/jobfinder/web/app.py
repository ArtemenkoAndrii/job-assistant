"""FastAPI application. Entry point: `uvicorn jobfinder.web.app:app`.

Every route except `/health` sits on the protected router: Origin check, then IAP token and owner
check (ADR-0008, ADR-0013). A new route is protected by default.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from jobfinder import __version__
from jobfinder.config import Settings, check_startup, get_settings
from jobfinder.storage.settings_repo import (
    FirestoreSettingsRepository,
    InMemorySettingsRepository,
    SettingsRepository,
)
from jobfinder.web.auth import Identity, KeyProvider, ensure_owner_record, require_owner
from jobfinder.web.csrf import check_origin

WEB_DIR = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=WEB_DIR / "templates")
STYLESHEET = WEB_DIR / "static" / "app.css"

NAV = (
    ("profiles", "Profiles", "/profiles"),
    ("settings", "Settings", "/settings"),
    ("runs", "Runs", "/runs"),
)


def authenticate(request: Request) -> Identity:
    identity = require_owner(request)
    ensure_owner_record(request, identity)
    return identity


def _page(request: Request, template: str, current: str) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, template, {"nav": NAV, "current": current})


def create_app(
    settings: Settings | None = None,
    key_provider: KeyProvider | None = None,
    settings_repo: SettingsRepository | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    check_startup(settings)

    app = FastAPI(
        title="Job Finder", version=__version__, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.settings = settings
    app.state.keys = key_provider or KeyProvider()
    app.state.settings_repo = settings_repo or (
        InMemorySettingsRepository() if settings.is_dev else FirestoreSettingsRepository()
    )
    app.state.owner_ready = False

    @app.exception_handler(StarletteHTTPException)
    async def refusal_page(request: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code in (401, 403):
            return TEMPLATES.TemplateResponse(
                request, "error.html", {"status": exc.status_code}, status_code=exc.status_code
            )
        return await http_exception_handler(request, exc)

    # Not /healthz: Cloud Run reserves paths ending in "z" (Cloud Run known issues).
    @app.get("/health")
    def health() -> dict[str, str]:
        """Liveness check for the hosting platform. Carries no data."""
        return {"status": "ok", "version": __version__}

    protected = APIRouter(dependencies=[Depends(check_origin), Depends(authenticate)])

    @protected.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse("/profiles", status_code=302)

    @protected.get("/profiles", response_class=HTMLResponse)
    def profiles(request: Request) -> HTMLResponse:
        return _page(request, "profiles.html", "profiles")

    @protected.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request) -> HTMLResponse:
        return _page(request, "settings.html", "settings")

    @protected.get("/runs", response_class=HTMLResponse)
    def runs(request: Request) -> HTMLResponse:
        return _page(request, "runs.html", "runs")

    # The stylesheet is served by the app, so it is behind the same checks as the pages.
    @protected.get("/static/app.css", include_in_schema=False)
    def stylesheet() -> FileResponse:
        return FileResponse(STYLESHEET, media_type="text/css")

    app.include_router(protected)
    return app


app = create_app()
