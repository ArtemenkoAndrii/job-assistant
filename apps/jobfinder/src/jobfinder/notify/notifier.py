"""Notifications (ADR-0010): events go to every enabled channel; one failing channel does not stop
the others. Nothing here logs a recipient, a token or a message body (NFR-P6)."""

import logging
from dataclasses import dataclass
from typing import Protocol

from jobfinder.domain.runs import Reason

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TestMessage:
    """The test message of the email check (#71)."""

    __test__ = False  # not a pytest test class

    subject: str = "Job Finder test message"
    body: str = "This is a test message from Job Finder.\nThe email sender works.\n"


Event = TestMessage


class ChannelError(Exception):
    """A channel could not deliver. `reason` is the code shown to the owner; no values inside."""

    def __init__(self, reason: Reason) -> None:
        super().__init__(reason.value)
        self.reason = reason


class Channel(Protocol):
    name: str

    def send(self, event: Event, recipient: str) -> None: ...


@dataclass(frozen=True)
class ChannelResult:
    channel: str
    reason: Reason | None  # None means delivered

    @property
    def ok(self) -> bool:
        return self.reason is None


class Notifier:
    def __init__(self, channels: list[Channel]) -> None:
        self._channels = channels

    def notify(self, event: Event, recipient: str) -> list[ChannelResult]:
        results: list[ChannelResult] = []
        for channel in self._channels:
            try:
                channel.send(event, recipient)
                results.append(ChannelResult(channel.name, None))
            except ChannelError as exc:
                results.append(ChannelResult(channel.name, exc.reason))
            except Exception as exc:
                log.warning("channel %s failed: %s", channel.name, type(exc).__name__)
                results.append(ChannelResult(channel.name, Reason.INTERNAL_ERROR))
        return results
