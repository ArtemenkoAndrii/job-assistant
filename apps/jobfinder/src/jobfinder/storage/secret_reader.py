"""Reading secrets at execution time through the Secret Manager API (spec #71, Design).

Nothing is injected into Cloud Run: three of the secrets have no version until the owner adds one,
and Cloud Run rejects a job update that references a secret without a version. The worker reads
a value only when the run kind needs it, so a missing value fails only that check.
"""

import base64
import threading
from typing import Any, Protocol

import httpx

from jobfinder.gcp import access_token

API = "https://secretmanager.googleapis.com/v1"
TIMEOUT_SECONDS = 10.0

A1_URL = "a1-url"
A1_CLIENT_ID = "a1-client-id"
A1_CLIENT_SECRET = "a1-client-secret"  # noqa: S105 (the secret's id, not its value)
EMAIL_SENDER = "email-sender"


class NotConfiguredError(Exception):
    """The secret or its version does not exist, or the version is disabled or destroyed."""


class SecretReadError(Exception):
    """Any other failure reading a secret. The message never carries a value."""


class SecretReader(Protocol):
    def read(self, name: str) -> str: ...


class InMemorySecretReader:
    """For tests and `dev` runs: only the names given have a value."""

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = dict(values or {})
        self.reads: list[str] = []
        self._lock = threading.Lock()

    def read(self, name: str) -> str:
        with self._lock:
            self.reads.append(name)
        try:
            return self.values[name]
        except KeyError:
            raise NotConfiguredError(name) from None


class SecretManagerReader:
    """Reads the `latest` version of a secret with the service's own ADC token."""

    def __init__(
        self,
        project: str,
        *,
        transport: httpx.BaseTransport | None = None,
        token: Any = None,
    ) -> None:
        self._project = project
        self._transport = transport
        self._token = token or access_token

    def read(self, name: str) -> str:
        url = f"{API}/projects/{self._project}/secrets/{name}/versions/latest:access"
        try:
            with httpx.Client(transport=self._transport, timeout=TIMEOUT_SECONDS) as http:
                response = http.get(url, headers={"Authorization": f"Bearer {self._token()}"})
        except Exception as exc:  # the message of a library error can contain the URL
            raise SecretReadError(type(exc).__name__) from None
        if response.status_code == 404:
            raise NotConfiguredError(name)
        if response.status_code == 400 and _status(response) == "FAILED_PRECONDITION":
            raise NotConfiguredError(name)
        if response.status_code != 200:
            raise SecretReadError(f"HTTP {response.status_code}")
        try:
            return base64.b64decode(response.json()["payload"]["data"]).decode()
        except Exception:
            raise SecretReadError("malformed response") from None


def _status(response: httpx.Response) -> str:
    try:
        return str(response.json()["error"]["status"])
    except Exception:
        return ""
