"""Access tokens for Google APIs from the service identity (Application Default Credentials)."""

import threading
from typing import Any

_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
_lock = threading.Lock()
_credentials: Any = None


def access_token() -> str:
    """A valid access token for the Cloud Run service account. google-auth caches and refreshes."""
    import google.auth
    import google.auth.transport.requests

    global _credentials
    with _lock:
        if _credentials is None:
            _credentials, _ = google.auth.default(scopes=[_SCOPE])
        if not _credentials.valid:
            _credentials.refresh(google.auth.transport.requests.Request())
        return str(_credentials.token)
