"""The check buttons and the card fragment (spec AC1-AC5, AC17, AC22)."""

import re
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from jobfinder.domain.runs import Reason, RunKind, RunStatus
from jobfinder.storage.runs_repo import InMemoryRunRepository
from jobfinder.web.auth import IAP_HEADER
from jobfinder.web.jobs import CloudRunJobStarter, JobStartError
from tests.conftest import HOST, FakeJobStarter

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
ORIGIN = {"origin": f"https://{HOST}"}


def post(client: TestClient, path: str, headers: dict[str, str], *, htmx: bool = True) -> Any:
    extra = {"hx-request": "true"} if htmx else {}
    return client.post(path, headers={**ORIGIN, **headers, **extra})


def test_settings_shows_both_buttons_and_not_run_yet(
    client: TestClient, owner_headers: Any
) -> None:
    html = client.get("/settings", headers=owner_headers).text
    assert "System checks" in html
    assert ">Check A-1</button>" in html
    assert ">Send test email</button>" in html
    assert html.count("Not run yet.") == 2


def test_pressing_check_a1_queues_one_validation_run_and_starts_the_worker(
    client: TestClient,
    owner_headers: Any,
    runs_repo: InMemoryRunRepository,
    job_starter: FakeJobStarter,
) -> None:
    response = post(client, "/checks/a1", owner_headers)
    assert response.status_code == 200
    assert "Waiting for the worker" in response.text
    (run,) = runs_repo.runs.values()
    assert (run.kind, run.status, run.trigger) == (RunKind.A1_CHECK, RunStatus.QUEUED, "validation")
    assert run.expire_at > run.created_at
    assert job_starter.calls == 1


def test_email_button_queues_an_email_test(
    client: TestClient, owner_headers: Any, runs_repo: InMemoryRunRepository
) -> None:
    post(client, "/checks/email", owner_headers)
    (run,) = runs_repo.runs.values()
    assert run.kind == RunKind.EMAIL_TEST


def test_second_press_while_active_creates_nothing(
    client: TestClient,
    owner_headers: Any,
    runs_repo: InMemoryRunRepository,
    job_starter: FakeJobStarter,
) -> None:
    post(client, "/checks/a1", owner_headers)
    again = post(client, "/checks/a1", owner_headers)
    assert again.status_code == 200
    assert len(runs_repo.runs) == 1
    assert job_starter.calls == 1
    runs_repo.mark_running(next(iter(runs_repo.runs)), NOW)
    post(client, "/checks/a1", owner_headers)
    assert len(runs_repo.runs) == 1
    assert "Running…" in client.get("/checks", headers=owner_headers).text


def test_start_failure_keeps_the_run_queued_and_says_so(
    client: TestClient,
    owner_headers: Any,
    runs_repo: InMemoryRunRepository,
    job_starter: FakeJobStarter,
) -> None:
    job_starter.fail = True
    response = post(client, "/checks/a1", owner_headers)
    assert response.status_code == 200
    assert "could not be started" in response.text
    assert "retry at the next scheduled start" in response.text
    (run,) = runs_repo.runs.values()
    assert run.status == RunStatus.QUEUED
    assert run.start_error


def test_without_htmx_the_post_redirects_back_to_settings(
    client: TestClient, owner_headers: Any
) -> None:
    response = post(client, "/checks/a1", owner_headers, htmx=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/settings"


@pytest.mark.parametrize("path", ["/checks/a1", "/checks/email"])
def test_refused_requests_create_no_run(
    client: TestClient,
    make_token: Any,
    owner_headers: Any,
    runs_repo: InMemoryRunRepository,
    job_starter: FakeJobStarter,
    path: str,
) -> None:
    assert client.post(path, headers=ORIGIN).status_code == 401
    other = {IAP_HEADER: make_token("someone@example.test")}
    assert client.post(path, headers={**ORIGIN, **other}).status_code == 403
    assert client.post(path, headers=owner_headers).status_code == 403  # no Origin
    foreign = {"origin": "https://evil.example", **owner_headers}
    assert client.post(path, headers=foreign).status_code == 403
    assert not runs_repo.runs
    assert job_starter.calls == 0


def test_card_states_after_results(
    client: TestClient, owner_headers: Any, runs_repo: InMemoryRunRepository
) -> None:
    run, _ = runs_repo.create_if_none_active(RunKind.A1_CHECK, NOW)
    runs_repo.finish(run.id, RunStatus.COMPLETED, NOW, snapshot_chars=1234)
    email, _ = runs_repo.create_if_none_active(RunKind.EMAIL_TEST, NOW)
    runs_repo.finish(email.id, RunStatus.FAILED, NOW, reason=Reason.EMAIL_AUTH, sent=False)
    html = client.get("/checks", headers=owner_headers).text
    assert "Passed. Snapshot received, 1234 characters." in html
    assert "27 Nov 2026, 12:00 UTC" in html
    assert "Failed. Gmail refused the sender&#39;s credential." in html
    assert "hx-trigger" not in html  # nothing active, so no polling
    assert "http" not in re.sub(r'href="/[^"]*"|src="/[^"]*"', "", html)  # nothing external


def test_card_polls_only_while_a_run_is_active(
    client: TestClient, owner_headers: Any, runs_repo: InMemoryRunRepository
) -> None:
    runs_repo.create_if_none_active(RunKind.A1_CHECK, NOW)
    html = client.get("/checks", headers=owner_headers).text
    assert 'hx-trigger="every 3s"' in html
    assert "disabled" in html


def test_cloud_run_job_starter_calls_the_run_endpoint() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    starter = CloudRunJobStarter(
        "123", "us-central1", token=lambda: "tok", transport=httpx.MockTransport(handle)
    )
    starter.start()
    assert str(seen[0].url) == (
        "https://run.googleapis.com/v2/projects/123/locations/us-central1/jobs/jobfinder-worker:run"
    )
    assert seen[0].headers["authorization"] == "Bearer tok"


@pytest.mark.parametrize("status", [403, 500])
def test_cloud_run_job_starter_failures(status: int) -> None:
    starter = CloudRunJobStarter(
        "123",
        "us-central1",
        token=lambda: "t",
        transport=httpx.MockTransport(lambda r: httpx.Response(status)),
    )
    with pytest.raises(JobStartError):
        starter.start()
