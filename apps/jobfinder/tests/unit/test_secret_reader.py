"""Secret Manager reads at execution time (spec AC21)."""

import base64

import httpx
import pytest

from jobfinder.storage.secret_reader import (
    InMemorySecretReader,
    NotConfiguredError,
    SecretManagerReader,
    SecretReadError,
)


def reader(transport: httpx.MockTransport) -> SecretManagerReader:
    return SecretManagerReader("123", transport=transport, token=lambda: "tok")


def test_reads_latest_version_and_decodes() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        data = base64.b64encode(b"value-1").decode()
        return httpx.Response(200, json={"payload": {"data": data}})

    assert reader(httpx.MockTransport(handle)).read("a1-url") == "value-1"
    assert str(seen[0].url).endswith("/projects/123/secrets/a1-url/versions/latest:access")
    assert seen[0].headers["authorization"] == "Bearer tok"


def test_missing_secret_or_version_is_not_configured() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(404, json={}))
    with pytest.raises(NotConfiguredError):
        reader(transport).read("a1-url")


def test_disabled_version_is_not_configured() -> None:
    body = {"error": {"status": "FAILED_PRECONDITION"}}
    transport = httpx.MockTransport(lambda r: httpx.Response(400, json=body))
    with pytest.raises(NotConfiguredError):
        reader(transport).read("a1-url")


@pytest.mark.parametrize("status", [401, 403, 500])
def test_other_http_errors_are_read_errors(status: int) -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(status, json={}))
    with pytest.raises(SecretReadError):
        reader(transport).read("a1-url")


def test_network_errors_do_not_leak_the_url() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("could not reach https://secretmanager.example/xyz")

    with pytest.raises(SecretReadError) as info:
        reader(httpx.MockTransport(boom)).read("a1-url")
    assert "secretmanager" not in str(info.value)


def test_in_memory_reader() -> None:
    fake = InMemorySecretReader({"a": "1"})
    assert fake.read("a") == "1"
    with pytest.raises(NotConfiguredError):
        fake.read("b")
    assert fake.reads == ["a", "b"]
