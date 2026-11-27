"""Daily page loads per job board (NFR-B5), in the `page_loads` collection (ADR-0007)."""

import threading
from datetime import datetime, timedelta
from typing import Any, Protocol

COLLECTION = "page_loads"
DAILY_LIMIT = 150
RETENTION = timedelta(days=365)


class PageLoadCounter(Protocol):
    def increment_if_below(self, board: str, now: datetime, limit: int = DAILY_LIMIT) -> bool:
        """Count one page load for `board` today unless the daily limit is reached."""
        ...


def _doc_id(board: str, now: datetime) -> str:
    return f"{board}-{now:%Y%m%d}"


class InMemoryPageLoadCounter:
    """For tests and `dev` runs."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def increment_if_below(self, board: str, now: datetime, limit: int = DAILY_LIMIT) -> bool:
        key = _doc_id(board, now)
        with self._lock:
            if self.counts.get(key, 0) >= limit:
                return False
            self.counts[key] = self.counts.get(key, 0) + 1
            return True


class FirestorePageLoadCounter:
    def __init__(self, client: Any = None) -> None:
        self._client = client

    def _db(self) -> Any:
        if self._client is None:
            from google.cloud import firestore

            self._client = firestore.Client()
        return self._client

    def increment_if_below(self, board: str, now: datetime, limit: int = DAILY_LIMIT) -> bool:
        from google.cloud import firestore

        db = self._db()
        ref = db.collection(COLLECTION).document(_doc_id(board, now))

        @firestore.transactional
        def txn(transaction: Any) -> bool:
            count = int((ref.get(transaction=transaction).to_dict() or {}).get("count", 0))
            if count >= limit:
                return False
            transaction.set(ref, {"count": count + 1, "expire_at": now + RETENTION})
            return True

        return txn(db.transaction())
