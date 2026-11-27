"""Starting the worker: one Cloud Run job execution through the Admin API (ADR-0006)."""

import logging
from collections.abc import Callable
from typing import Protocol

import httpx

from jobfinder.gcp import access_token

log = logging.getLogger(__name__)

JOB_NAME = "jobfinder-worker"
TIMEOUT_SECONDS = 15.0


class JobStartError(Exception):
    """The worker execution could not be started. The run stays queued for the next tick."""


class JobStarter(Protocol):
    def start(self) -> None: ...


class CloudRunJobStarter:
    """`POST .../jobs/jobfinder-worker:run` with the web service's own identity (`run.invoker`)."""

    def __init__(
        self,
        project_number: str,
        region: str,
        *,
        token: Callable[[], str] = access_token,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = (
            f"https://run.googleapis.com/v2/projects/{project_number}"
            f"/locations/{region}/jobs/{JOB_NAME}:run"
        )
        self._token = token
        self._transport = transport

    def start(self) -> None:
        try:
            with httpx.Client(transport=self._transport, timeout=TIMEOUT_SECONDS) as http:
                response = http.post(
                    self._url, json={}, headers={"Authorization": f"Bearer {self._token()}"}
                )
        except Exception as exc:
            raise JobStartError(type(exc).__name__) from None
        if response.status_code != 200:
            raise JobStartError(f"HTTP {response.status_code}")


class NoopJobStarter:
    """For `dev` runs: there is no worker to start."""

    def start(self) -> None:
        log.info("dev: not starting a worker execution")
