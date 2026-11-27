"""The run lease on `locks/worker` (ADR-0007): one worker execution at a time (NFR-R2)."""

import threading
from datetime import datetime, timedelta
from typing import Any, Protocol

LEASE_TTL = timedelta(minutes=10)
RENEW_EVERY = timedelta(minutes=2)
COLLECTION = "locks"
DOCUMENT = "worker"


class Lease(Protocol):
    def take(self, holder: str, now: datetime) -> bool:
        """Take the lease if it is free or expired. Returns whether `holder` now has it."""
        ...

    def renew(self, holder: str, now: datetime) -> bool:
        """Extend the lease if `holder` still has it. Returns False if it was lost."""
        ...

    def release(self, holder: str) -> None:
        """Free the lease if `holder` has it."""
        ...


class InMemoryLease:
    """For tests and `dev` runs."""

    def __init__(self) -> None:
        self.holder: str | None = None
        self.expires_at: datetime | None = None
        self._lock = threading.Lock()

    def take(self, holder: str, now: datetime) -> bool:
        with self._lock:
            if self.holder is not None and self.expires_at is not None and now < self.expires_at:
                return False
            self.holder = holder
            self.expires_at = now + LEASE_TTL
            return True

    def renew(self, holder: str, now: datetime) -> bool:
        with self._lock:
            if self.holder != holder:
                return False
            self.expires_at = now + LEASE_TTL
            return True

    def release(self, holder: str) -> None:
        with self._lock:
            if self.holder == holder:
                self.holder = None
                self.expires_at = None


class FirestoreLease:
    """Firestore implementation: every change is a transaction on one document."""

    def __init__(self, client: Any = None) -> None:
        self._client = client

    def _db(self) -> Any:
        if self._client is None:
            from google.cloud import firestore

            self._client = firestore.Client()
        return self._client

    def _ref(self) -> Any:
        return self._db().collection(COLLECTION).document(DOCUMENT)

    def take(self, holder: str, now: datetime) -> bool:
        from google.cloud import firestore

        ref = self._ref()

        @firestore.transactional
        def txn(transaction: Any) -> bool:
            data = ref.get(transaction=transaction).to_dict() or {}
            expires_at = data.get("expires_at")
            if data.get("holder") and expires_at is not None and now < expires_at:
                return False
            transaction.set(ref, {"holder": holder, "expires_at": now + LEASE_TTL})
            return True

        return txn(self._db().transaction())

    def renew(self, holder: str, now: datetime) -> bool:
        from google.cloud import firestore

        ref = self._ref()

        @firestore.transactional
        def txn(transaction: Any) -> bool:
            data = ref.get(transaction=transaction).to_dict() or {}
            if data.get("holder") != holder:
                return False
            transaction.update(ref, {"expires_at": now + LEASE_TTL})
            return True

        return txn(self._db().transaction())

    def release(self, holder: str) -> None:
        from google.cloud import firestore

        ref = self._ref()

        @firestore.transactional
        def txn(transaction: Any) -> None:
            data = ref.get(transaction=transaction).to_dict() or {}
            if data.get("holder") == holder:
                transaction.set(ref, {"holder": None, "expires_at": None})

        txn(self._db().transaction())
