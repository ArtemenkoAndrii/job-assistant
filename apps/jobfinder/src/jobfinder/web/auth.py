"""IAP token verification and the owner check (ADR-0008 §2). Every failure denies access."""

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import HTTPException, Request
from jwt.algorithms import ECAlgorithm

from jobfinder.config import Settings

log = logging.getLogger(__name__)

IAP_JWK_URL = "https://www.gstatic.com/iap/verify/public_key-jwk"
IAP_ISSUER = "https://cloud.google.com/iap"
IAP_HEADER = "x-goog-iap-jwt-assertion"
LEEWAY_SECONDS = 30
KEY_TTL_SECONDS = 3600
MIN_REFRESH_SECONDS = 60
FETCH_TIMEOUT_SECONDS = 3.0
DEV_EMAIL = "dev@example.test"


@dataclass(frozen=True)
class Identity:
    email: str


class KeyProvider:
    """IAP's public keys by `kid`: fetched lazily, cached, refreshed once on an unknown `kid`.

    `fetch` returns the JWK document; it is injectable so tests make no network call.
    """

    def __init__(self, fetch: Callable[[], dict[str, Any]] | None = None) -> None:
        self._fetch = fetch or _fetch_iap_keys
        self._keys: dict[str, Any] = {}
        self._loaded_at = 0.0
        self._lock = threading.Lock()

    def get(self, kid: str) -> Any | None:
        with self._lock:
            now = time.monotonic()
            expired = now - self._loaded_at > KEY_TTL_SECONDS
            if kid in self._keys and not expired:
                return self._keys[kid]
            if expired or now - self._loaded_at > MIN_REFRESH_SECONDS:
                self._load(now)
            return self._keys.get(kid)

    def _load(self, now: float) -> None:
        self._loaded_at = now  # also rate-limits retries after a failed fetch
        try:
            document = self._fetch()
            self._keys = {
                key["kid"]: ECAlgorithm.from_jwk(json.dumps(key))
                for key in document["keys"]
                if key.get("kty") == "EC"
            }
        except Exception:
            log.warning("could not load IAP public keys")
            self._keys = {}


def _fetch_iap_keys() -> dict[str, Any]:
    response = httpx.get(IAP_JWK_URL, timeout=FETCH_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def verify_iap_jwt(token: str, keys: KeyProvider, settings: Settings) -> Identity:
    """Return the verified identity or raise `jwt.PyJWTError`/`ValueError`."""
    header = jwt.get_unverified_header(token)
    if header.get("alg") != "ES256":
        raise ValueError("unexpected algorithm")
    kid = header.get("kid")
    if not isinstance(kid, str):
        raise ValueError("no key id")
    key = keys.get(kid)
    if key is None:
        raise ValueError("unknown key id")
    claims = jwt.decode(
        token,
        key,
        algorithms=["ES256"],
        audience=settings.iap_audience,
        issuer=IAP_ISSUER,
        leeway=LEEWAY_SECONDS,
        options={"require": ["exp", "iat", "iss", "aud", "email"]},
    )
    email = claims["email"]
    if not isinstance(email, str) or not email:
        raise ValueError("no email")
    return Identity(email=email.lower())


def require_owner(request: Request) -> Identity:
    """FastAPI dependency: 401 without a valid IAP token, 403 for anyone but the owner.

    Reasons are logged as codes only: never the email, the token or the owner setting (NFR-P6).
    """
    settings: Settings = request.app.state.settings
    if settings.is_dev:
        return Identity(email=DEV_EMAIL)

    token = request.headers.get(IAP_HEADER)
    if not token:
        log.info("auth refused: no token")
        raise HTTPException(status_code=401)
    try:
        identity = verify_iap_jwt(token, request.app.state.keys, settings)
    except jwt.PyJWTError, ValueError:
        log.info("auth refused: invalid token")
        raise HTTPException(status_code=401) from None

    owner = settings.owner_email.strip().lower()
    if not owner or identity.email != owner:
        log.info("auth refused: not the owner")
        raise HTTPException(status_code=403)
    return identity


def ensure_owner_record(request: Request, identity: Identity) -> None:
    """First sign-in creates `settings/owner` (UC-01). Never blocks the page or logs the email."""
    state = request.app.state
    if state.owner_ready:
        return
    try:
        state.settings_repo.ensure_owner(identity.email)
    except Exception:
        log.warning("could not ensure settings/owner")
        return
    state.owner_ready = True
