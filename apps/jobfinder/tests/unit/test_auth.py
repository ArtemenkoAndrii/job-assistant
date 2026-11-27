import logging
from collections.abc import Callable
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from jobfinder.web.auth import IAP_HEADER
from tests.conftest import AUDIENCE, OWNER

PATH = "/profiles"


def test_no_token_is_401(client: TestClient) -> None:
    assert client.get(PATH).status_code == 401


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "/projects/1/locations/us-central1/services/other"},
        {"aud": AUDIENCE.replace("123456789", "999")},
        {"iss": "https://accounts.example.test"},
        {"exp_in": -3600},
        {"kid": "unknown"},
    ],
    ids=["aud-service", "aud-project", "iss", "expired", "kid"],
)
def test_bad_token_is_401(
    client: TestClient, make_token: Callable[..., str], overrides: dict[str, Any]
) -> None:
    response = client.get(PATH, headers={IAP_HEADER: make_token(**overrides)})
    assert response.status_code == 401


def test_other_signing_key_is_401(client: TestClient, make_token: Callable[..., str]) -> None:
    other = ec.generate_private_key(ec.SECP256R1())
    assert client.get(PATH, headers={IAP_HEADER: make_token(key=other)}).status_code == 401


def test_other_algorithms_are_401(client: TestClient, make_token: Callable[..., str]) -> None:
    hs256 = jwt.encode(
        {
            "email": OWNER,
            "aud": AUDIENCE,
            "iss": "https://cloud.google.com/iap",
            "iat": 1,
            "exp": 4102444800,
        },
        "x" * 32,
        algorithm="HS256",
        headers={"kid": "test-key"},
    )
    unsigned = jwt.encode(
        {"email": OWNER, "aud": AUDIENCE},
        None,  # type: ignore[arg-type]  # the "none" algorithm takes no key
        algorithm="none",
        headers={"kid": "test-key"},
    )
    for token in (hs256, unsigned, "not-a-jwt"):
        assert client.get(PATH, headers={IAP_HEADER: token}).status_code == 401


def test_other_email_is_403_and_spoofed_header_is_ignored(
    client: TestClient, make_token: Callable[..., str]
) -> None:
    headers = {
        IAP_HEADER: make_token("someone@example.test"),
        "x-goog-authenticated-user-email": f"accounts.google.com:{OWNER}",
    }
    assert client.get(PATH, headers=headers).status_code == 403


def test_owner_is_200_case_insensitive(
    make_client: Callable[..., TestClient], make_token: Callable[..., str]
) -> None:
    client = make_client(owner_email=OWNER.upper())
    response = client.get(PATH, headers={IAP_HEADER: make_token(OWNER.title())})
    assert response.status_code == 200
    assert "No profiles yet" in response.text


@pytest.mark.parametrize("owner", ["", "   "])
def test_empty_owner_setting_refuses_everyone(
    make_client: Callable[..., TestClient], make_token: Callable[..., str], repo: Any, owner: str
) -> None:
    repo.ensure_owner(OWNER)  # settings/owner exists: it must play no part
    client = make_client(owner_email=owner)
    assert client.get(PATH, headers={IAP_HEADER: make_token()}).status_code == 403
    assert client.get(PATH, headers={IAP_HEADER: make_token("")}).status_code in (401, 403)


def test_dev_mode_uses_the_stand_in_identity(make_client: Callable[..., TestClient]) -> None:
    client = make_client(environment="dev")
    assert client.get(PATH).status_code == 200


def test_responses_and_logs_never_contain_email_or_token(
    client: TestClient, make_token: Callable[..., str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    other_token = make_token("someone@example.test")
    owner_token = make_token()
    responses = [
        client.get(PATH),
        client.get(PATH, headers={IAP_HEADER: other_token}),
        client.get(PATH, headers={IAP_HEADER: "garbage"}),
        client.get(PATH, headers={IAP_HEADER: owner_token}),
    ]
    secrets = [OWNER, "someone@example.test", other_token, owner_token]
    assert [r.status_code for r in responses] == [401, 403, 401, 200]
    for response in responses[:2]:
        assert not any(s in response.text for s in secrets)
    assert not any(s in caplog.text for s in secrets)


def test_failed_refresh_keeps_known_keys_and_stays_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    signing_key: ec.EllipticCurvePrivateKey,
    make_token: Callable[..., str],
) -> None:
    import json

    from jwt.algorithms import ECAlgorithm

    from jobfinder.config import Settings
    from jobfinder.web import auth
    from jobfinder.web.auth import KEY_TTL_SECONDS, KeyProvider, verify_iap_jwt
    from tests.conftest import KID, PROJECT_NUMBER

    jwk = json.loads(ECAlgorithm.to_jwk(signing_key.public_key()))
    jwk["kid"] = KID
    outage = False

    def fetch() -> dict[str, Any]:
        if outage:
            raise OSError("www.gstatic.com unreachable")
        return {"keys": [jwk]}

    clock = [1000.0]
    monkeypatch.setattr(auth.time, "monotonic", lambda: clock[0])
    settings = Settings(owner_email=OWNER, project_number=PROJECT_NUMBER)
    keys = KeyProvider(fetch=fetch)
    token = make_token()

    assert verify_iap_jwt(token, keys, settings).email == OWNER  # keys loaded

    clock[0] += KEY_TTL_SECONDS + 1  # TTL expired
    outage = True  # and the fetch fails
    assert verify_iap_jwt(token, keys, settings).email == OWNER  # known kid still verifies
    with pytest.raises(ValueError):  # an unknown kid is still refused
        verify_iap_jwt(make_token(kid="unknown"), keys, settings)

    # Without any keys (fetch failing from the start) every token is refused.
    empty = KeyProvider(fetch=fetch)
    with pytest.raises(ValueError):
        verify_iap_jwt(token, empty, settings)


def test_keys_load_on_a_freshly_started_machine(
    monkeypatch: pytest.MonkeyPatch,
    key_provider: Any,
    make_token: Callable[..., str],
) -> None:
    """The monotonic clock may be near zero right after boot; the first fetch must still happen."""
    from jobfinder.config import Settings
    from jobfinder.web import auth
    from jobfinder.web.auth import verify_iap_jwt
    from tests.conftest import PROJECT_NUMBER

    monkeypatch.setattr(auth.time, "monotonic", lambda: 5.0)
    settings = Settings(owner_email=OWNER, project_number=PROJECT_NUMBER)
    assert verify_iap_jwt(make_token(), key_provider, settings).email == OWNER
