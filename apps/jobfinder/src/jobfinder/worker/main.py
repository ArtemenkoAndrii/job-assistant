"""The worker's run loop (ADR-0007): take the lease, execute one queued run, release the lease.

One run per execution keeps every run inside the job timeout. Logs carry run ids, kinds and reason
codes only: never an address, a token, a host or a page (NFR-P6).
"""

import logging
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from jobfinder.browser.gateway import BrowserBlockedError, BrowserGateway
from jobfinder.browser.mcp_session import McpSession
from jobfinder.domain.runs import Reason, Run, RunKind, RunStatus
from jobfinder.notify.email_channel import EmailCredentials, parse_credentials
from jobfinder.notify.notifier import Channel, ChannelError, Notifier, TestMessage
from jobfinder.storage.lease import RENEW_EVERY, Lease
from jobfinder.storage.page_loads import PageLoadCounter
from jobfinder.storage.runs_repo import RunRepository
from jobfinder.storage.secret_reader import (
    A1_CLIENT_ID,
    A1_CLIENT_SECRET,
    A1_URL,
    EMAIL_SENDER,
    NotConfiguredError,
    SecretReader,
    SecretReadError,
)
from jobfinder.storage.settings_repo import SettingsRepository

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class Dependencies:
    runs: RunRepository
    lease: Lease
    secrets: SecretReader
    settings: SettingsRepository
    counter: PageLoadCounter
    session_factory: Callable[[str, str, str], McpSession]
    channel_factory: Callable[[EmailCredentials], Channel]
    holder: str
    clock: Callable[[], datetime] = _utcnow
    renew_every_seconds: float = RENEW_EVERY.total_seconds()
    sleep: Callable[[float], None] = time.sleep
    uniform: Callable[[float, float], float] = random.uniform


@dataclass(frozen=True)
class Outcome:
    status: RunStatus
    reason: Reason | None = None
    snapshot_chars: int | None = None
    sent: bool | None = None


def run_once(deps: Dependencies) -> int:
    """Execute at most one queued run. Returns the process exit code."""
    if not deps.lease.take(deps.holder, deps.clock()):
        log.info("another worker holds the lease; exiting")
        return 0
    lost = threading.Event()
    stop = threading.Event()
    renewer = threading.Thread(target=_renew, args=(deps, lost, stop), daemon=True)
    renewer.start()
    try:
        stale = deps.runs.fail_stale_running(deps.clock())
        if stale:
            log.warning("marked %d crashed run(s) as failed", stale)
        run = deps.runs.oldest_queued()
        if run is None:
            log.info("no queued run")
            return 0
        deps.runs.mark_running(run.id, deps.clock())
        outcome = _execute(deps, run)
        if lost.is_set():
            outcome = Outcome(RunStatus.STOPPED, Reason.LEASE_LOST)
        deps.runs.finish(
            run.id,
            outcome.status,
            deps.clock(),
            reason=outcome.reason,
            snapshot_chars=outcome.snapshot_chars,
            sent=outcome.sent,
        )
        log.info(
            "run %s (%s): %s %s", run.id, run.kind.value, outcome.status.value, outcome.reason or ""
        )
        return 0
    finally:
        stop.set()
        renewer.join(timeout=5)
        deps.lease.release(deps.holder)


def _renew(deps: Dependencies, lost: threading.Event, stop: threading.Event) -> None:
    while not stop.wait(deps.renew_every_seconds):
        try:
            if not deps.lease.renew(deps.holder, deps.clock()):
                lost.set()
                return
        except Exception as exc:
            log.warning("lease renewal failed: %s", type(exc).__name__)
            lost.set()
            return


def _execute(deps: Dependencies, run: Run) -> Outcome:
    try:
        if run.kind == RunKind.A1_CHECK:
            return _a1_check(deps)
        return _email_test(deps)
    except Exception as exc:
        log.warning("run %s failed: %s", run.id, type(exc).__name__)
        return Outcome(RunStatus.FAILED, Reason.INTERNAL_ERROR)


def _a1_check(deps: Dependencies) -> Outcome:
    try:
        url = deps.secrets.read(A1_URL)
        client_id = deps.secrets.read(A1_CLIENT_ID)
        client_secret = deps.secrets.read(A1_CLIENT_SECRET)
    except NotConfiguredError:
        return Outcome(RunStatus.FAILED, Reason.A1_NOT_CONFIGURED)
    except SecretReadError:
        return Outcome(RunStatus.FAILED, Reason.A1_UNREACHABLE)
    session = deps.session_factory(url, client_id, client_secret)
    try:
        gateway = BrowserGateway(
            session, deps.counter, sleep=deps.sleep, uniform=deps.uniform, clock=deps.clock
        )
        chars = gateway.check_search_page()
    except BrowserBlockedError as blocked:
        return Outcome(RunStatus.FAILED, blocked.reason)
    finally:
        session.close()
    return Outcome(RunStatus.COMPLETED, snapshot_chars=chars)


def _email_test(deps: Dependencies) -> Outcome:
    try:
        credentials = parse_credentials(deps.secrets.read(EMAIL_SENDER))
    except NotConfiguredError:
        return Outcome(RunStatus.FAILED, Reason.EMAIL_NOT_CONFIGURED)
    except SecretReadError:
        return Outcome(RunStatus.FAILED, Reason.EMAIL_SEND_FAILED)
    except ChannelError as error:
        return Outcome(RunStatus.FAILED, error.reason)
    recipient = deps.settings.notification_email()
    if not recipient:
        return Outcome(RunStatus.FAILED, Reason.NO_NOTIFICATION_EMAIL)
    result = Notifier([deps.channel_factory(credentials)]).notify(TestMessage(), recipient)[0]
    if result.ok:
        return Outcome(RunStatus.COMPLETED, sent=True)
    return Outcome(RunStatus.FAILED, result.reason, sent=False)
