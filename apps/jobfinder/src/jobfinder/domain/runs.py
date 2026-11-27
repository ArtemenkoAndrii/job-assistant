"""Validation runs (spec #71): kinds, statuses, reason codes and the card text for each reason."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

RETENTION = timedelta(
    days=30
)  # a validation record is operational; ADR-0007 caps runs at 12 months
TRIGGER_VALIDATION = "validation"


class RunKind(StrEnum):
    A1_CHECK = "a1_check"
    EMAIL_TEST = "email_test"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


ACTIVE = frozenset({RunStatus.QUEUED, RunStatus.RUNNING})


class Reason(StrEnum):
    A1_NOT_CONFIGURED = "a1_not_configured"
    A1_UNREACHABLE = "a1_unreachable"
    A1_AUTH = "a1_auth"
    LOGIN_WALL = "login_wall"
    CHALLENGE = "challenge"
    EMPTY_SNAPSHOT = "empty_snapshot"
    DAILY_LIMIT = "daily_limit"
    OFF_POLICY = "off_policy"
    EMAIL_NOT_CONFIGURED = "email_not_configured"
    EMAIL_AUTH = "email_auth"
    EMAIL_SEND_FAILED = "email_send_failed"
    NO_NOTIFICATION_EMAIL = "no_notification_email"
    WORKER_CRASHED = "worker_crashed"
    LEASE_LOST = "lease_lost"
    INTERNAL_ERROR = "internal_error"


REASON_TEXT: dict[Reason, str] = {
    Reason.A1_NOT_CONFIGURED: "A-1 is not configured.",
    Reason.A1_UNREACHABLE: "A-1 did not answer. Is the home server running?",
    Reason.A1_AUTH: "A-1 refused the service token.",
    Reason.LOGIN_WALL: "LinkedIn asked for a sign-in. Sign in to A-1's browser again.",
    Reason.CHALLENGE: "LinkedIn showed a human check. Try again later.",
    Reason.EMPTY_SNAPSHOT: "The page came back empty.",
    Reason.DAILY_LIMIT: "The daily page-load limit is reached.",
    Reason.OFF_POLICY: "The browser went to a page that is not allowed.",
    Reason.EMAIL_NOT_CONFIGURED: "The email sender is not configured.",
    Reason.EMAIL_AUTH: "Gmail refused the sender's credential. It needs a new consent.",
    Reason.EMAIL_SEND_FAILED: "Gmail could not send the message.",
    Reason.NO_NOTIFICATION_EMAIL: "No notification email is saved yet.",
    Reason.WORKER_CRASHED: "The worker stopped during the check.",
    Reason.LEASE_LOST: "The worker lost its lock and stopped.",
    Reason.INTERNAL_ERROR: "Something went wrong in the worker.",
}


@dataclass
class Run:
    id: str
    kind: RunKind
    status: RunStatus
    created_at: datetime
    expire_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    reason: Reason | None = None
    snapshot_chars: int | None = None
    sent: bool | None = None
    start_error: bool = False
    trigger: str = TRIGGER_VALIDATION

    @property
    def active(self) -> bool:
        return self.status in ACTIVE
