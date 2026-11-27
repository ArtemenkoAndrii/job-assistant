"""The worker run loop with fakes only (spec AC6-AC9, AC14-AC16, AC21)."""

import json
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from jobfinder.browser.mcp_session import McpUnreachableError, ToolResult
from jobfinder.domain.runs import Reason, Run, RunKind, RunStatus
from jobfinder.notify.notifier import ChannelError, Event
from jobfinder.storage.lease import InMemoryLease
from jobfinder.storage.page_loads import InMemoryPageLoadCounter
from jobfinder.storage.runs_repo import InMemoryRunRepository
from jobfinder.storage.secret_reader import InMemorySecretReader
from jobfinder.storage.settings_repo import InMemorySettingsRepository
from jobfinder.worker.main import Dependencies, run_once

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
A1_HOST = "a1-private-host.example"
TOKEN = "service-token-value"  # noqa: S105
RECIPIENT = "owner-private@example.test"
BODY = "PAGE-TEXT-SENTINEL " + "- listitem 'Software Engineer at Acme' " * 10
SENDER_JSON = json.dumps(
    {"client_id": "c", "client_secret": "s", "refresh_token": "r", "sender": "sender@example.test"}
)
A1_SECRETS = {
    "a1-url": f"https://{A1_HOST}/mcp",
    "a1-client-id": "client-id-value",
    "a1-client-secret": TOKEN,
}


class FakeSession:
    def __init__(self, results: list[ToolResult | Exception], delay: float = 0.0) -> None:
        self.results = results
        self.delay = delay
        self.calls: list[str] = []
        self.closed = False

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        time.sleep(self.delay)
        self.calls.append(name)
        item = self.results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self) -> None:
        self.closed = True


class FakeChannel:
    name = "fake"

    def __init__(self, error: ChannelError | None = None) -> None:
        self.error = error
        self.sent: list[tuple[Event, str]] = []

    def send(self, event: Event, recipient: str) -> None:
        if self.error:
            raise self.error
        self.sent.append((event, recipient))


def page(body: str = BODY, title: str = "Jobs") -> ToolResult:
    url = "https://www.linkedin.com/jobs/search/?keywords=software%20engineer&f_TPR=r604800"
    return ToolResult(f"- Page URL: {url}\n- Page Title: {title}\n{body}")


class Harness:
    def __init__(self, **overrides: Any) -> None:
        self.runs = InMemoryRunRepository()
        self.lease = InMemoryLease()
        self.secrets = InMemorySecretReader({**A1_SECRETS, "email-sender": SENDER_JSON})
        self.settings = InMemorySettingsRepository()
        self.settings.ensure_owner(RECIPIENT)
        self.counter = InMemoryPageLoadCounter()
        self.session = FakeSession([page(), page()])
        self.channel = FakeChannel()
        self.sessions_made = 0
        values: dict[str, Any] = {
            "runs": self.runs,
            "lease": self.lease,
            "secrets": self.secrets,
            "settings": self.settings,
            "counter": self.counter,
            "session_factory": self.make_session,
            "channel_factory": lambda creds: self.channel,
            "holder": "worker-1",
            "clock": lambda: NOW,
            "sleep": lambda s: None,
            "uniform": lambda a, b: 1.0,
        }
        values.update(overrides)
        self.deps = Dependencies(**values)

    def make_session(self, url: str, cid: str, secret: str) -> FakeSession:
        self.sessions_made += 1
        return self.session

    def queue(self, kind: RunKind) -> Run:
        run, _ = self.runs.create_if_none_active(kind, NOW)
        return run

    def stored(self, run: Run) -> Run:
        return self.runs.runs[run.id]


def test_executes_the_oldest_queued_run_and_releases_the_lease() -> None:
    h = Harness()
    first = h.queue(RunKind.EMAIL_TEST)
    second = h.runs.create_if_none_active(RunKind.A1_CHECK, NOW + timedelta(seconds=1))[0]
    assert run_once(h.deps) == 0
    assert h.stored(first).status == RunStatus.COMPLETED
    assert h.stored(second).status == RunStatus.QUEUED  # one run per execution
    assert h.lease.holder is None


def test_nothing_queued_exits_cleanly_and_releases() -> None:
    h = Harness()
    assert run_once(h.deps) == 0
    assert h.lease.holder is None


def test_second_worker_exits_without_touching_runs() -> None:
    h = Harness()
    run = h.queue(RunKind.A1_CHECK)
    h.lease.take("other-worker", NOW)
    assert run_once(h.deps) == 0
    assert h.stored(run).status == RunStatus.QUEUED
    assert h.lease.holder == "other-worker"
    assert h.sessions_made == 0


def test_crashed_run_is_failed_before_the_next_one_runs() -> None:
    h = Harness()
    crashed = h.queue(RunKind.A1_CHECK)
    h.runs.mark_running(crashed.id, NOW - timedelta(hours=1))
    waiting = h.queue(RunKind.EMAIL_TEST)
    run_once(h.deps)
    assert h.stored(crashed).status == RunStatus.FAILED
    assert h.stored(crashed).reason == Reason.WORKER_CRASHED
    assert h.stored(waiting).status == RunStatus.COMPLETED


def test_a1_check_succeeds_with_snapshot_size_and_counter() -> None:
    h = Harness()
    run = h.queue(RunKind.A1_CHECK)
    run_once(h.deps)
    stored = h.stored(run)
    assert stored.status == RunStatus.COMPLETED
    assert stored.snapshot_chars and stored.snapshot_chars > 100
    assert h.counter.counts == {"linkedin-20261127": 1}
    assert h.session.calls == ["browser_navigate", "browser_snapshot"]
    assert h.session.closed


@pytest.mark.parametrize(
    ("results", "reason"),
    [
        ([page(title="Just a moment...")], Reason.CHALLENGE),
        ([page(body="Sign in to view more jobs")], Reason.LOGIN_WALL),
        ([McpUnreachableError("HTTP 502")], Reason.A1_UNREACHABLE),
    ],
)
def test_a1_check_failures_are_recorded_with_a_reason(
    results: list[ToolResult | Exception], reason: Reason
) -> None:
    h = Harness(session_factory=lambda u, c, s: FakeSession(results))
    run = h.queue(RunKind.A1_CHECK)
    run_once(h.deps)
    assert h.stored(run).status == RunStatus.FAILED
    assert h.stored(run).reason == reason


@pytest.mark.parametrize("missing", ["a1-url", "a1-client-id", "a1-client-secret"])
def test_missing_a1_secret_fails_without_creating_the_gateway(missing: str) -> None:
    h = Harness()
    del h.secrets.values[missing]
    run = h.queue(RunKind.A1_CHECK)
    run_once(h.deps)
    assert h.stored(run).reason == Reason.A1_NOT_CONFIGURED
    assert h.sessions_made == 0
    assert h.counter.counts == {}


def test_email_test_sends_one_message_to_the_notification_email() -> None:
    h = Harness()
    run = h.queue(RunKind.EMAIL_TEST)
    run_once(h.deps)
    assert h.stored(run).status == RunStatus.COMPLETED
    assert h.stored(run).sent is True
    assert [recipient for _, recipient in h.channel.sent] == [RECIPIENT]
    assert h.sessions_made == 0
    assert "a1-url" not in h.secrets.reads  # only what the kind needs


def test_missing_email_sender_fails_not_configured() -> None:
    h = Harness()
    del h.secrets.values["email-sender"]
    run = h.queue(RunKind.EMAIL_TEST)
    run_once(h.deps)
    assert h.stored(run).reason == Reason.EMAIL_NOT_CONFIGURED


def test_malformed_email_sender_fails_not_configured() -> None:
    h = Harness()
    h.secrets.values["email-sender"] = "not json"
    run = h.queue(RunKind.EMAIL_TEST)
    run_once(h.deps)
    assert h.stored(run).reason == Reason.EMAIL_NOT_CONFIGURED


def test_channel_errors_are_recorded() -> None:
    h = Harness()
    h.channel.error = ChannelError(Reason.EMAIL_AUTH)
    run = h.queue(RunKind.EMAIL_TEST)
    run_once(h.deps)
    assert h.stored(run).status == RunStatus.FAILED
    assert h.stored(run).reason == Reason.EMAIL_AUTH
    assert h.stored(run).sent is False


def test_no_notification_email_fails() -> None:
    h = Harness(settings=InMemorySettingsRepository())
    run = h.queue(RunKind.EMAIL_TEST)
    run_once(h.deps)
    assert h.stored(run).reason == Reason.NO_NOTIFICATION_EMAIL


def test_unexpected_error_is_recorded_without_details(caplog: pytest.LogCaptureFixture) -> None:
    def boom(url: str, cid: str, secret: str) -> FakeSession:
        raise RuntimeError(f"details {TOKEN} {A1_HOST}")

    h = Harness(session_factory=boom)
    run = h.queue(RunKind.A1_CHECK)
    with caplog.at_level(logging.DEBUG):
        run_once(h.deps)
    assert h.stored(run).reason == Reason.INTERNAL_ERROR
    assert TOKEN not in caplog.text
    assert A1_HOST not in caplog.text


def test_losing_the_lease_stops_the_run() -> None:
    class LosingLease(InMemoryLease):
        def renew(self, holder: str, now: datetime) -> bool:
            return False

    h = Harness(lease=LosingLease(), renew_every_seconds=0.01)
    h.session.delay = 0.2
    run = h.queue(RunKind.A1_CHECK)
    run_once(h.deps)
    assert h.stored(run).status == RunStatus.STOPPED
    assert h.stored(run).reason == Reason.LEASE_LOST


@pytest.mark.parametrize("kind", list(RunKind))
def test_no_secret_address_host_or_text_in_logs_or_records(
    kind: RunKind, caplog: pytest.LogCaptureFixture
) -> None:
    h = Harness()
    run = h.queue(kind)
    with caplog.at_level(logging.DEBUG):
        run_once(h.deps)
    stored = repr(h.stored(run))
    for value in (TOKEN, A1_HOST, RECIPIENT, "PAGE-TEXT-SENTINEL", "client-id-value"):
        assert value not in caplog.text
        assert value not in stored
