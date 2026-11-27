"""The `settings/owner` record (ADR-0007), created on the owner's first sign-in (UC-01 step 2)."""

import threading
from typing import Any, Protocol


class SettingsRepository(Protocol):
    def ensure_owner(self, email: str) -> bool:
        """Create `settings/owner` with `email` as notification email if it does not exist.

        Never overwrites an existing record. Returns True if this call created it.
        """
        ...

    def notification_email(self) -> str | None:
        """The notification email from `settings/owner`, or None if there is no record yet."""
        ...


class InMemorySettingsRepository:
    """For tests and `dev` runs."""

    def __init__(self) -> None:
        self.owner: dict[str, Any] | None = None
        self._lock = threading.Lock()

    def ensure_owner(self, email: str) -> bool:
        with self._lock:
            if self.owner is not None:
                return False
            self.owner = {"notification_email": email}
            return True

    def notification_email(self) -> str | None:
        with self._lock:
            return None if self.owner is None else self.owner.get("notification_email")


class FirestoreSettingsRepository:
    """Firestore implementation. The client is imported and created lazily, so the app starts
    without paying for it until the first sign-in."""

    def __init__(self, client: Any = None) -> None:
        self._client = client

    def ensure_owner(self, email: str) -> bool:
        from google.api_core.exceptions import AlreadyExists
        from google.cloud import firestore

        if self._client is None:
            self._client = firestore.Client()
        ref = self._client.collection("settings").document("owner")
        try:
            ref.create({"notification_email": email, "created_at": firestore.SERVER_TIMESTAMP})
        except AlreadyExists:
            return False
        return True

    def notification_email(self) -> str | None:
        from google.cloud import firestore

        if self._client is None:
            self._client = firestore.Client()
        data = self._client.collection("settings").document("owner").get().to_dict() or {}
        value = data.get("notification_email")
        return str(value) if value else None
