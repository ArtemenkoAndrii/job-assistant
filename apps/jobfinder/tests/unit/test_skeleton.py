"""Smoke tests: the web app and the worker start."""

import pytest
from fastapi.testclient import TestClient

from jobfinder import __version__
from jobfinder.web.app import app
from jobfinder.worker.__main__ import main as worker_main


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_api_docs_are_not_public() -> None:
    assert TestClient(app).get("/docs").status_code == 404


def test_worker_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBFINDER_ENVIRONMENT", "dev")
    monkeypatch.delenv("K_SERVICE", raising=False)
    assert worker_main() == 0
