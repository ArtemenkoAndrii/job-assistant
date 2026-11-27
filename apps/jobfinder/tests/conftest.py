"""Shared fixtures: test IAP signing key, token helper, app factory. No network, no Firestore."""

import json
import time
from collections.abc import Callable
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from jwt.algorithms import ECAlgorithm

from jobfinder.config import Settings
from jobfinder.storage.settings_repo import InMemorySettingsRepository
from jobfinder.web.app import create_app
from jobfinder.web.auth import IAP_HEADER, IAP_ISSUER, KeyProvider

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


@pytest.fixture
def make_client(
    key_provider: KeyProvider, repo: InMemorySettingsRepository
) -> Callable[..., TestClient]:
    def make(**overrides: Any) -> TestClient:
        values: dict[str, Any] = {
            "environment": "production",
            "owner_email": OWNER,
            "project_number": PROJECT_NUMBER,
        }
        values.update(overrides)
        app = create_app(Settings(**values), key_provider=key_provider, settings_repo=repo)
        return TestClient(app, base_url=f"https://{HOST}", follow_redirects=False)

    return make


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()


@pytest.fixture
def owner_headers(make_token: Callable[..., str]) -> dict[str, str]:
    return {IAP_HEADER: make_token()}
