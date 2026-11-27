"""The email channel: Gmail API with scope `gmail.send` from the dedicated sender (ADR-0010)."""

import base64
import json
from dataclasses import dataclass
from email.message import EmailMessage

import httpx

from jobfinder.domain.runs import Reason
from jobfinder.notify.notifier import ChannelError, Event

TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 (a URL, not a credential)
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class EmailCredentials:
    client_id: str
    client_secret: str
    refresh_token: str
    sender: str

    def __repr__(self) -> str:  # never print values
        return "EmailCredentials(...)"


def parse_credentials(raw: str) -> EmailCredentials:
    """Parse the `email-sender` JSON. Anything malformed means *not configured*."""
    try:
        data = json.loads(raw)
        creds = EmailCredentials(
            client_id=str(data["client_id"]),
            client_secret=str(data["client_secret"]),
            refresh_token=str(data["refresh_token"]),
            sender=str(data["sender"]),
        )
    except Exception:
        raise ChannelError(Reason.EMAIL_NOT_CONFIGURED) from None
    if not all((creds.client_id, creds.client_secret, creds.refresh_token, creds.sender)):
        raise ChannelError(Reason.EMAIL_NOT_CONFIGURED)
    return creds


class EmailChannel:
    name = "email"

    def __init__(
        self, credentials: EmailCredentials, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._creds = credentials
        self._transport = transport

    def send(self, event: Event, recipient: str) -> None:
        message = EmailMessage()
        message["From"] = self._creds.sender
        message["To"] = recipient
        message["Subject"] = event.subject
        message.set_content(event.body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        try:
            with httpx.Client(transport=self._transport, timeout=TIMEOUT_SECONDS) as http:
                token = self._access_token(http)
                response = http.post(
                    SEND_URL, json={"raw": raw}, headers={"Authorization": f"Bearer {token}"}
                )
        except ChannelError:
            raise
        except Exception:  # a library message can contain the URL
            raise ChannelError(Reason.EMAIL_SEND_FAILED) from None
        if response.status_code == 401:
            raise ChannelError(Reason.EMAIL_AUTH)
        if response.status_code != 200:
            raise ChannelError(Reason.EMAIL_SEND_FAILED)

    def _access_token(self, http: httpx.Client) -> str:
        response = http.post(
            TOKEN_URL,
            data={
                "client_id": self._creds.client_id,
                "client_secret": self._creds.client_secret,
                "refresh_token": self._creds.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if response.status_code in (400, 401):
            raise ChannelError(Reason.EMAIL_AUTH)  # invalid_grant, invalid_client
        if response.status_code != 200:
            raise ChannelError(Reason.EMAIL_SEND_FAILED)
        try:
            return str(response.json()["access_token"])
        except Exception:
            raise ChannelError(Reason.EMAIL_SEND_FAILED) from None
