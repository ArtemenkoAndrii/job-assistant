import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from google.api_core.exceptions import AlreadyExists

from jobfinder.storage.settings_repo import (
    FirestoreSettingsRepository,
    InMemorySettingsRepository,
)
from jobfinder.web.auth import IAP_HEADER
from tests.conftest import OWNER


def test_first_sign_in_creates_the_record(
    client: TestClient, repo: Any, owner_headers: Any
) -> None:
    assert repo.owner is None
    assert client.get("/profiles", headers=owner_headers).status_code == 200
    assert repo.owner == {"notification_email": OWNER}


def test_existing_record_is_not_changed(client: TestClient, repo: Any, owner_headers: Any) -> None:
    repo.owner = {"notification_email": "other@example.test"}
    client.get("/profiles", headers=owner_headers)
    assert repo.owner == {"notification_email": "other@example.test"}


def test_concurrent_first_requests_create_one_record() -> None:
    repo = InMemorySettingsRepository()
    with ThreadPoolExecutor(8) as pool:
        created = list(pool.map(repo.ensure_owner, [OWNER] * 8))
    assert created.count(True) == 1


def test_firestore_failure_does_not_block_the_page(
    make_client: Callable[..., TestClient],
    owner_headers: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class Broken:
        def ensure_owner(self, email: str) -> bool:
            raise RuntimeError(f"unavailable {email}")

    client = make_client()
    client.app.state.settings_repo = Broken()  # type: ignore[attr-defined]
    caplog.set_level(logging.DEBUG)
    response = client.get("/profiles", headers=owner_headers)
    assert response.status_code == 200
    assert OWNER not in caplog.text
    assert client.app.state.owner_ready is False  # type: ignore[attr-defined]


def test_non_owner_does_not_create_the_record(
    client: TestClient, repo: Any, make_token: Callable[..., str]
) -> None:
    client.get("/profiles", headers={IAP_HEADER: make_token("someone@example.test")})
    assert repo.owner is None


class FakeDocument:
    def __init__(self, exists: bool) -> None:
        self.exists = exists
        self.created: dict[str, Any] | None = None

    def create(self, data: dict[str, Any]) -> None:
        if self.exists:
            raise AlreadyExists("exists")
        self.created = data


class FakeClient:
    def __init__(self, doc: FakeDocument) -> None:
        self.doc = doc
        self.path: list[str] = []

    def collection(self, name: str) -> FakeClient:
        self.path.append(name)
        return self

    def document(self, name: str) -> FakeDocument:
        self.path.append(name)
        return self.doc


def test_firestore_repo_creates_if_absent_and_never_overwrites() -> None:
    fresh = FakeClient(FakeDocument(exists=False))
    assert FirestoreSettingsRepository(fresh).ensure_owner(OWNER) is True
    assert fresh.path == ["settings", "owner"]
    assert fresh.doc.created is not None
    assert fresh.doc.created["notification_email"] == OWNER

    existing = FakeClient(FakeDocument(exists=True))
    assert FirestoreSettingsRepository(existing).ensure_owner(OWNER) is False
    assert existing.doc.created is None
