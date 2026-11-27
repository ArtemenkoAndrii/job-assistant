"""The network guard in conftest.py blocks everything but localhost (spec AC20)."""

import socket

import pytest

from tests.conftest import NetworkBlockedError


@pytest.mark.parametrize("host", ["93.184.216.34", "example.com", "2001:db8::1"])
def test_outside_address_is_blocked(host: str) -> None:
    with socket.socket() as sock, pytest.raises(NetworkBlockedError):
        sock.connect((host, 80))


def test_connect_ex_is_blocked_too() -> None:
    with socket.socket() as sock, pytest.raises(NetworkBlockedError):
        sock.connect_ex(("93.184.216.34", 80))


def test_localhost_is_allowed() -> None:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        with socket.socket() as client:
            client.connect(server.getsockname())
