"""Run queue behaviour on the in-memory repository (spec AC2, AC3, AC6-AC8 at repository level)."""

from datetime import UTC, datetime, timedelta

from jobfinder.domain.runs import RETENTION, Reason, RunKind, RunStatus
from jobfinder.storage.runs_repo import InMemoryRunRepository

T0 = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


def test_create_queues_a_validation_run_with_expiry() -> None:
    repo = InMemoryRunRepository()
    run, created = repo.create_if_none_active(RunKind.A1_CHECK, T0)
    assert created
    assert run.status == RunStatus.QUEUED
    assert run.trigger == "validation"
    assert run.kind == RunKind.A1_CHECK
    assert run.expire_at == T0 + RETENTION


def test_no_second_run_while_one_is_queued_or_running() -> None:
    repo = InMemoryRunRepository()
    first, _ = repo.create_if_none_active(RunKind.A1_CHECK, T0)
    again, created = repo.create_if_none_active(RunKind.A1_CHECK, T0 + timedelta(seconds=5))
    assert not created
    assert again.id == first.id

    repo.mark_running(first.id, T0)
    again, created = repo.create_if_none_active(RunKind.A1_CHECK, T0 + timedelta(seconds=9))
    assert not created
    assert again.id == first.id
    assert len(repo.runs) == 1


def test_kinds_are_independent_and_finished_runs_allow_a_new_one() -> None:
    repo = InMemoryRunRepository()
    a1, _ = repo.create_if_none_active(RunKind.A1_CHECK, T0)
    email, created = repo.create_if_none_active(RunKind.EMAIL_TEST, T0)
    assert created
    assert email.id != a1.id

    repo.finish(a1.id, RunStatus.COMPLETED, T0, snapshot_chars=10)
    nxt, created = repo.create_if_none_active(RunKind.A1_CHECK, T0 + timedelta(minutes=1))
    assert created
    assert nxt.id != a1.id
    assert repo.latest(RunKind.A1_CHECK) == nxt


def test_oldest_queued_first() -> None:
    repo = InMemoryRunRepository()
    assert repo.oldest_queued() is None
    older, _ = repo.create_if_none_active(RunKind.EMAIL_TEST, T0)
    repo.create_if_none_active(RunKind.A1_CHECK, T0 + timedelta(seconds=1))
    assert repo.oldest_queued() == older
    repo.mark_running(older.id, T0)
    nxt = repo.oldest_queued()
    assert nxt is not None
    assert nxt.kind == RunKind.A1_CHECK


def test_finish_records_result_fields() -> None:
    repo = InMemoryRunRepository()
    run, _ = repo.create_if_none_active(RunKind.A1_CHECK, T0)
    repo.finish(run.id, RunStatus.FAILED, T0, reason=Reason.LOGIN_WALL)
    stored = repo.latest(RunKind.A1_CHECK)
    assert stored is not None
    assert stored.status == RunStatus.FAILED
    assert stored.reason == Reason.LOGIN_WALL
    assert stored.finished_at == T0


def test_stale_running_runs_are_failed_as_crashed() -> None:
    repo = InMemoryRunRepository()
    run, _ = repo.create_if_none_active(RunKind.A1_CHECK, T0)
    repo.mark_running(run.id, T0)
    assert repo.fail_stale_running(T0 + timedelta(hours=1)) == 1
    stored = repo.latest(RunKind.A1_CHECK)
    assert stored is not None
    assert stored.status == RunStatus.FAILED
    assert stored.reason == Reason.WORKER_CRASHED


def test_start_error_flag() -> None:
    repo = InMemoryRunRepository()
    run, _ = repo.create_if_none_active(RunKind.A1_CHECK, T0)
    repo.set_start_error(run.id)
    assert repo.runs[run.id].start_error
