"""The `runs` collection and the queue over it (ADR-0007), for validation runs (#71)."""

import threading
import uuid
from datetime import datetime
from typing import Any, Protocol

from jobfinder.domain.runs import (
    RETENTION,
    Reason,
    Run,
    RunKind,
    RunStatus,
)

COLLECTION = "runs"


class RunRepository(Protocol):
    def create_if_none_active(self, kind: RunKind, now: datetime) -> tuple[Run, bool]:
        """Queue a run of `kind`, unless one is already queued or running.

        Returns the run and whether this call created it.
        """
        ...

    def latest(self, kind: RunKind) -> Run | None: ...

    def oldest_queued(self) -> Run | None: ...

    def mark_running(self, run_id: str, now: datetime) -> None: ...

    def finish(
        self,
        run_id: str,
        status: RunStatus,
        now: datetime,
        *,
        reason: Reason | None = None,
        snapshot_chars: int | None = None,
        sent: bool | None = None,
    ) -> None: ...

    def fail_stale_running(self, now: datetime) -> int:
        """Mark runs left `running` by a crashed execution as failed. Returns how many."""
        ...

    def set_start_error(self, run_id: str) -> None: ...


def _new_run(kind: RunKind, now: datetime) -> Run:
    return Run(
        id=uuid.uuid4().hex,
        kind=kind,
        status=RunStatus.QUEUED,
        created_at=now,
        expire_at=now + RETENTION,
    )


class InMemoryRunRepository:
    """For tests and `dev` runs."""

    def __init__(self) -> None:
        self.runs: dict[str, Run] = {}
        self._lock = threading.Lock()

    def create_if_none_active(self, kind: RunKind, now: datetime) -> tuple[Run, bool]:
        with self._lock:
            current = self._latest(kind)
            if current is not None and current.active:
                return current, False
            run = _new_run(kind, now)
            self.runs[run.id] = run
            return run, True

    def _latest(self, kind: RunKind) -> Run | None:
        of_kind = [r for r in self.runs.values() if r.kind == kind]
        return max(of_kind, key=lambda r: r.created_at, default=None)

    def latest(self, kind: RunKind) -> Run | None:
        with self._lock:
            return self._latest(kind)

    def oldest_queued(self) -> Run | None:
        with self._lock:
            queued = [r for r in self.runs.values() if r.status == RunStatus.QUEUED]
            return min(queued, key=lambda r: r.created_at, default=None)

    def mark_running(self, run_id: str, now: datetime) -> None:
        with self._lock:
            run = self.runs[run_id]
            run.status = RunStatus.RUNNING
            run.started_at = now

    def finish(
        self,
        run_id: str,
        status: RunStatus,
        now: datetime,
        *,
        reason: Reason | None = None,
        snapshot_chars: int | None = None,
        sent: bool | None = None,
    ) -> None:
        with self._lock:
            run = self.runs[run_id]
            run.status = status
            run.finished_at = now
            run.reason = reason
            run.snapshot_chars = snapshot_chars
            run.sent = sent

    def fail_stale_running(self, now: datetime) -> int:
        with self._lock:
            stale = [r for r in self.runs.values() if r.status == RunStatus.RUNNING]
            for run in stale:
                run.status = RunStatus.FAILED
                run.finished_at = now
                run.reason = Reason.WORKER_CRASHED
            return len(stale)

    def set_start_error(self, run_id: str) -> None:
        with self._lock:
            self.runs[run_id].start_error = True


def _to_run(doc_id: str, data: dict[str, Any]) -> Run:
    result = data.get("result") or {}
    reason = result.get("reason")
    return Run(
        id=doc_id,
        kind=RunKind(data["kind"]),
        status=RunStatus(data["status"]),
        created_at=data["created_at"],
        expire_at=data["expire_at"],
        started_at=data.get("started_at"),
        finished_at=data.get("finished_at"),
        reason=Reason(reason) if reason else None,
        snapshot_chars=result.get("snapshot_chars"),
        sent=result.get("sent"),
        start_error=bool(data.get("start_error", False)),
        trigger=data.get("trigger", "validation"),
    )


class FirestoreRunRepository:
    """Firestore implementation. The client is created lazily, as in `FirestoreSettingsRepository`.

    Queries need the composite indexes in `infra/app/indexes.tf`: (status, created_at) and
    (kind, created_at desc).
    """

    def __init__(self, client: Any = None) -> None:
        self._client = client

    def _db(self) -> Any:
        if self._client is None:
            from google.cloud import firestore

            self._client = firestore.Client()
        return self._client

    def _latest_query(self, kind: RunKind) -> Any:
        from google.cloud import firestore

        return (
            self._db()
            .collection(COLLECTION)
            .where("kind", "==", kind.value)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(1)
        )

    def create_if_none_active(self, kind: RunKind, now: datetime) -> tuple[Run, bool]:
        from google.cloud import firestore

        db = self._db()
        new = _new_run(kind, now)

        @firestore.transactional
        def txn(transaction: Any) -> tuple[Run, bool]:
            for doc in self._latest_query(kind).get(transaction=transaction):
                current = _to_run(doc.id, doc.to_dict())
                if current.active:
                    return current, False
            transaction.create(
                db.collection(COLLECTION).document(new.id),
                {
                    "trigger": new.trigger,
                    "kind": new.kind.value,
                    "status": new.status.value,
                    "created_at": new.created_at,
                    "expire_at": new.expire_at,
                },
            )
            return new, True

        return txn(db.transaction())

    def latest(self, kind: RunKind) -> Run | None:
        for doc in self._latest_query(kind).get():
            return _to_run(doc.id, doc.to_dict())
        return None

    def oldest_queued(self) -> Run | None:
        from google.cloud import firestore

        query = (
            self._db()
            .collection(COLLECTION)
            .where("status", "==", RunStatus.QUEUED.value)
            .order_by("created_at", direction=firestore.Query.ASCENDING)
            .limit(1)
        )
        for doc in query.get():
            return _to_run(doc.id, doc.to_dict())
        return None

    def mark_running(self, run_id: str, now: datetime) -> None:
        self._db().collection(COLLECTION).document(run_id).update(
            {"status": RunStatus.RUNNING.value, "started_at": now}
        )

    def finish(
        self,
        run_id: str,
        status: RunStatus,
        now: datetime,
        *,
        reason: Reason | None = None,
        snapshot_chars: int | None = None,
        sent: bool | None = None,
    ) -> None:
        result: dict[str, Any] = {"ok": status == RunStatus.COMPLETED}
        if reason is not None:
            result["reason"] = reason.value
        if snapshot_chars is not None:
            result["snapshot_chars"] = snapshot_chars
        if sent is not None:
            result["sent"] = sent
        self._db().collection(COLLECTION).document(run_id).update(
            {"status": status.value, "finished_at": now, "result": result}
        )

    def fail_stale_running(self, now: datetime) -> int:
        docs = list(
            self._db().collection(COLLECTION).where("status", "==", RunStatus.RUNNING.value).get()
        )
        for doc in docs:
            self.finish(doc.id, RunStatus.FAILED, now, reason=Reason.WORKER_CRASHED)
        return len(docs)

    def set_start_error(self, run_id: str) -> None:
        self._db().collection(COLLECTION).document(run_id).update({"start_error": True})
