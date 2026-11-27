"""The "System checks" card on the Settings page: two buttons, their latest results (spec #71).

The routes sit on the protected router (Origin check, IAP token, owner). The web service only
queues a run and starts the worker; it never browses and never sends email.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from jobfinder.domain.runs import REASON_TEXT, Reason, Run, RunKind, RunStatus
from jobfinder.storage.runs_repo import RunRepository
from jobfinder.web.jobs import JobStarter, JobStartError

log = logging.getLogger(__name__)

router = APIRouter()

TITLES = {
    RunKind.A1_CHECK: ("A-1 browser", "Opens one LinkedIn search page through A-1.", "Check A-1"),
    RunKind.EMAIL_TEST: (
        "Email",
        "Sends one test message to your notification email.",
        "Send test email",
    ),
}


@dataclass(frozen=True)
class CheckView:
    kind: str
    title: str
    description: str
    button: str
    status_text: str
    symbol: str
    busy: bool


def _when(moment: datetime | None) -> str:
    return "" if moment is None else f" ({moment.astimezone(UTC):%d %b %Y, %H:%M} UTC)"


def _view(kind: RunKind, run: Run | None) -> CheckView:
    title, description, button = TITLES[kind]
    text, symbol, busy = "Not run yet.", "", False
    if run is not None:
        if run.status == RunStatus.QUEUED:
            busy, symbol = True, "…"
            text = (
                "The worker could not be started. It will retry at the next scheduled start."
                if run.start_error
                else "Waiting for the worker…"
            )
        elif run.status == RunStatus.RUNNING:
            busy, symbol, text = True, "…", "Running…"
        elif run.status == RunStatus.COMPLETED:
            symbol = "✓"
            if kind == RunKind.A1_CHECK:
                text = (
                    f"Passed. Snapshot received, {run.snapshot_chars} characters."
                    f"{_when(run.finished_at)}"
                )
            else:
                text = f"Message sent. Check your inbox.{_when(run.finished_at)}"
        else:
            symbol = "✕"
            reason = run.reason or Reason.INTERNAL_ERROR
            text = f"Failed. {REASON_TEXT[reason]}{_when(run.finished_at)}"
    return CheckView(kind.value, title, description, button, text, symbol, busy)


def checks_context(runs: RunRepository) -> dict[str, object]:
    views = [_view(kind, runs.latest(kind)) for kind in (RunKind.A1_CHECK, RunKind.EMAIL_TEST)]
    return {"checks": views, "polling": any(v.busy for v in views)}


def _fragment(request: Request) -> HTMLResponse:
    templates: Jinja2Templates = request.app.state.templates
    context = checks_context(request.app.state.runs)
    return templates.TemplateResponse(request, "_checks.html", context)


@router.get("/checks", response_class=HTMLResponse)
def show_checks(request: Request) -> HTMLResponse:
    return _fragment(request)


def _queue(request: Request, kind: RunKind) -> Response:
    runs: RunRepository = request.app.state.runs
    starter: JobStarter = request.app.state.job_starter
    run, created = runs.create_if_none_active(kind, datetime.now(UTC))
    if created:
        try:
            starter.start()
        except JobStartError as exc:
            log.warning("could not start the worker: %s", exc)
            runs.set_start_error(run.id)
    if "hx-request" in request.headers:
        return _fragment(request)
    return RedirectResponse("/settings", status_code=303)


@router.post("/checks/a1", response_class=HTMLResponse)
def check_a1(request: Request) -> Response:
    return _queue(request, RunKind.A1_CHECK)


@router.post("/checks/email", response_class=HTMLResponse)
def check_email(request: Request) -> Response:
    return _queue(request, RunKind.EMAIL_TEST)
