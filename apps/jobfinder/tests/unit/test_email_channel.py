"""Gmail channel over a mock transport (spec AC14-AC16)."""

import base64
import email
import json
from email.message import Message

import httpx
import pytest

from jobfinder.domain.runs import Reason
from jobfinder.notify.email_channel import (
    SEND_URL,
    TOKEN_URL,
    EmailChannel,
    EmailCredentials,
    parse_credentials,
)
from jobfinder.notify.notifier import ChannelError, TestMessage

CREDS = EmailCredentials("cid", "csecret", "refresh-1", "sender@example.test")


def channel(handler: httpx.MockTransport) -> EmailChannel:
    return EmailChannel(CREDS, transport=handler)


def test_sends_one_message_from_the_sender_to_the_recipient() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if str(request.url) == TOKEN_URL:
            return httpx.Response(200, json={"access_token": "access-1"})
        assert str(request.url) == SEND_URL
        return httpx.Response(200, json={"id": "m1"})

    channel(httpx.MockTransport(handle)).send(TestMessage(), "owner@example.test")
    assert [str(r.url) for r in seen] == [TOKEN_URL, SEND_URL]
    assert b"grant_type=refresh_token" in seen[0].content
    assert seen[1].headers["authorization"] == "Bearer access-1"
    raw = json.loads(seen[1].content)["raw"]
    message: Message = email.message_from_bytes(base64.urlsafe_b64decode(raw))
    assert message["From"] == "sender@example.test"
    assert message["To"] == "owner@example.test"
    assert message["Subject"] == "Job Finder test message"


@pytest.mark.parametrize(
    ("token_status", "send_status", "expected"),
    [
        (400, 0, Reason.EMAIL_AUTH),  # invalid_grant
        (401, 0, Reason.EMAIL_AUTH),
        (500, 0, Reason.EMAIL_SEND_FAILED),
        (200, 401, Reason.EMAIL_AUTH),
        (200, 403, Reason.EMAIL_SEND_FAILED),
        (200, 500, Reason.EMAIL_SEND_FAILED),
    ],
)
def test_errors_map_to_reasons(token_status: int, send_status: int, expected: Reason) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            body = {"access_token": "a"} if token_status == 200 else {"error": "invalid_grant"}
            return httpx.Response(token_status, json=body)
        return httpx.Response(send_status, json={})

    with pytest.raises(ChannelError) as info:
        channel(httpx.MockTransport(handle)).send(TestMessage(), "owner@example.test")
    assert info.value.reason == expected


def test_network_error_is_a_send_failure_without_details() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("cannot reach https://gmail.example")

    with pytest.raises(ChannelError) as info:
        channel(httpx.MockTransport(boom)).send(TestMessage(), "owner@example.test")
    assert info.value.reason == Reason.EMAIL_SEND_FAILED
    assert "gmail" not in str(info.value)


def test_credentials_parse_and_never_print() -> None:
    raw = json.dumps(
        {"client_id": "c", "client_secret": "s", "refresh_token": "r", "sender": "a@example.test"}
    )
    creds = parse_credentials(raw)
    assert creds.sender == "a@example.test"
    assert "a@example.test" not in repr(creds)
    assert "r" not in repr(creds).replace("EmailCredentials", "")


@pytest.mark.parametrize("raw", ["not json", "{}", json.dumps({"client_id": "c"}), "[1]"])
def test_malformed_credentials_are_not_configured(raw: str) -> None:
    with pytest.raises(ChannelError) as info:
        parse_credentials(raw)
    assert info.value.reason == Reason.EMAIL_NOT_CONFIGURED
