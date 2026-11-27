"""Origin check for state-changing requests (ADR-0013, replacing ADR-0008 §5's list)."""

import logging

from fastapi import HTTPException, Request

from jobfinder.config import Settings

log = logging.getLogger(__name__)

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def check_origin(request: Request) -> None:
    """`Origin` must equal "https://" + Host (also "http://" + Host in `dev` only).

    `X-Forwarded-Host` is never used. A missing `Origin` or `Host` is refused.
    """
    if request.method in SAFE_METHODS:
        return
    settings: Settings = request.app.state.settings
    origin = request.headers.get("origin")
    host = request.headers.get("host")
    if not origin or not host:
        log.info("origin refused: missing")
        raise HTTPException(status_code=403)
    allowed = {f"https://{host.lower()}"}
    if settings.is_dev:
        allowed.add(f"http://{host.lower()}")
    if origin.lower() not in allowed:
        log.info("origin refused: mismatch")
        raise HTTPException(status_code=403)
