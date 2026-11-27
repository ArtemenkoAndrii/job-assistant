"""Shared fixtures: test IAP signing key, token helper, app factory. No network, no Firestore.

An autouse fixture blocks every socket connection except to localhost (NFR-M5, spec AC20), so a
test that reaches A-1, LinkedIn, Gmail or Google fails instead of calling out.
"""

import json
import socket
import time
from collections.abc import Callable
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from jwt.algorithms import ECAlgorithm

from jobfinder.config import Settings
from jobfinder.storage.runs_repo import InMemoryRunRepository
from jobfinder.storage.settings_repo import InMemorySettingsRepository
from jobfinder.web.app import create_app
from jobfinder.web.auth import IAP_HEADER, IAP_ISSUER, KeyProvider
from jobfinder.web.jobs import JobStartError

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class NetworkBlockedError(RuntimeError):
    """A test tried to connect to something other than localhost."""


@pytest.fixture(autouse=True)
def block_outside_network(monkeypatch: pytest.MonkeyPatch) -> None:
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def check(address: Any) -> None:
        # A string or bytes address is a Unix socket path: local by definition.
        if isinstance(address, tuple) and str(address[0]) not in LOCAL_HOSTS:
            msg = f"tests may only connect to localhost, not {address[0]!r}"
            raise NetworkBlockedError(msg)

    def connect(self: socket.socket, address: Any) -> None:
        check(address)
        real_connect(self, address)

    def connect_ex(self: socket.socket, address: Any) -> int:
        check(address)
        return real_connect_ex(self, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)


PROJECT_NUMBER = "123456789"
OWNER = "owner@example.test"
KID = "test-key"
HOST = "jobfinder-web-123456789.us-central1.run.app"
AUDIENCE = f"/projects/{PROJECT_NUMBER}/locations/us-central1/services/jobfinder-web"


@pytest.fixture(scope="session")
def signing_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def make_token(signing_key: ec.EllipticCurvePrivateKey) -> Callable[..., str]:
    def make(
        email: str = OWNER,
        *,
        aud: str = AUDIENCE,
        iss: str = IAP_ISSUER,
        exp_in: int = 600,
        kid: str = KID,
        key: Any = None,
        alg: str = "ES256",
    ) -> str:
        now = int(time.time())
        claims = {"email": email, "aud": aud, "iss": iss, "iat": now, "exp": now + exp_in}
        return jwt.encode(claims, key or signing_key, algorithm=alg, headers={"kid": kid})

    return make


@pytest.fixture
def key_provider(signing_key: ec.EllipticCurvePrivateKey) -> KeyProvider:
    jwk = json.loads(ECAlgorithm.to_jwk(signing_key.public_key()))
    jwk["kid"] = KID
    return KeyProvider(fetch=lambda: {"keys": [jwk]})


@pytest.fixture
def repo() -> InMemorySettingsRepository:
    return InMemorySettingsRepository()


class FakeJobStarter:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    def start(self) -> None:
        self.calls += 1
        if self.fail:
            raise JobStartError("HTTP 500")


@pytest.fixture
def runs_repo() -> InMemoryRunRepository:
    return InMemoryRunRepository()


@pytest.fixture
def job_starter() -> FakeJobStarter:
    return FakeJobStarter()


@pytest.fixture
def make_client(
    key_provider: KeyProvider,
    repo: InMemorySettingsRepository,
    runs_repo: InMemoryRunRepository,
    job_starter: FakeJobStarter,
) -> Callable[..., TestClient]:
    def make(**overrides: Any) -> TestClient:
        values: dict[str, Any] = {
            "environment": "production",
            "owner_email": OWNER,
            "project_number": PROJECT_NUMBER,
        }
        values.update(overrides)
        app = create_app(
            Settings(**values),
            key_provider=key_provider,
            settings_repo=repo,
            runs_repo=runs_repo,
            job_starter=job_starter,
        )
        return TestClient(app, base_url=f"https://{HOST}", follow_redirects=False)

    return make


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()


@pytest.fixture
def owner_headers(make_token: Callable[..., str]) -> dict[str, str]:
    return {IAP_HEADER: make_token()}
