"""Worker entry point: `python -m jobfinder.worker`. Starts, runs at most one queued run, exits."""

import logging
import os
import sys
import uuid

from jobfinder.config import get_settings
from jobfinder.worker.main import Dependencies, run_once


def build_dev() -> Dependencies:
    """In-memory dependencies for the CI smoke test and local runs (`JOBFINDER_ENVIRONMENT=dev`)."""
    from jobfinder.browser.mcp_session import HttpMcpSession
    from jobfinder.notify.email_channel import EmailChannel
    from jobfinder.storage.lease import InMemoryLease
    from jobfinder.storage.page_loads import InMemoryPageLoadCounter
    from jobfinder.storage.runs_repo import InMemoryRunRepository
    from jobfinder.storage.secret_reader import InMemorySecretReader
    from jobfinder.storage.settings_repo import InMemorySettingsRepository

    return Dependencies(
        runs=InMemoryRunRepository(),
        lease=InMemoryLease(),
        secrets=InMemorySecretReader(),
        settings=InMemorySettingsRepository(),
        counter=InMemoryPageLoadCounter(),
        session_factory=lambda url, cid, secret: HttpMcpSession(url, cid, secret),
        channel_factory=lambda creds: EmailChannel(creds),
        holder=uuid.uuid4().hex,
    )


def build() -> Dependencies:
    from jobfinder.browser.mcp_session import HttpMcpSession
    from jobfinder.notify.email_channel import EmailChannel
    from jobfinder.storage.lease import FirestoreLease
    from jobfinder.storage.page_loads import FirestorePageLoadCounter
    from jobfinder.storage.runs_repo import FirestoreRunRepository
    from jobfinder.storage.secret_reader import SecretManagerReader
    from jobfinder.storage.settings_repo import FirestoreSettingsRepository

    settings = get_settings()
    return Dependencies(
        runs=FirestoreRunRepository(),
        lease=FirestoreLease(),
        secrets=SecretManagerReader(settings.project_number),
        settings=FirestoreSettingsRepository(),
        counter=FirestorePageLoadCounter(),
        session_factory=lambda url, cid, secret: HttpMcpSession(url, cid, secret),
        channel_factory=lambda creds: EmailChannel(creds),
        holder=os.environ.get("CLOUD_RUN_EXECUTION") or uuid.uuid4().hex,
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return run_once(build_dev() if get_settings().is_dev else build())


if __name__ == "__main__":
    sys.exit(main())
