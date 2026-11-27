"""Notifier fan-out (ADR-0010; spec AC14, AC15)."""

import logging

import pytest

from jobfinder.domain.runs import Reason
from jobfinder.notify.notifier import ChannelError, Event, Notifier, TestMessage


class FakeChannel:
    def __init__(self, name: str = "fake", error: Exception | None = None) -> None:
        self.name = name
        self.error = error
        self.sent: list[tuple[Event, str]] = []

    def send(self, event: Event, recipient: str) -> None:
        if self.error:
            raise self.error
        self.sent.append((event, recipient))


def test_every_channel_gets_the_event() -> None:
    a, b = FakeChannel("a"), FakeChannel("b")
    results = Notifier([a, b]).notify(TestMessage(), "me@example.test")
    assert all(r.ok for r in results)
    assert a.sent == b.sent == [(TestMessage(), "me@example.test")]


def test_a_failing_channel_does_not_stop_the_others(caplog: pytest.LogCaptureFixture) -> None:
    bad = FakeChannel("bad", RuntimeError("secret detail me@example.test"))
    declined = FakeChannel("declined", ChannelError(Reason.EMAIL_AUTH))
    good = FakeChannel("good")
    with caplog.at_level(logging.DEBUG):
        results = Notifier([bad, declined, good]).notify(TestMessage(), "me@example.test")
    assert [(r.channel, r.reason) for r in results] == [
        ("bad", Reason.INTERNAL_ERROR),
        ("declined", Reason.EMAIL_AUTH),
        ("good", None),
    ]
    assert len(good.sent) == 1
    assert "me@example.test" not in caplog.text
    assert "secret detail" not in caplog.text
