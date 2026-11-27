"""The Streamable HTTP client against a mock transport (spec AC12)."""

import json

import httpx
import pytest

from jobfinder.browser.mcp_session import HttpMcpSession, McpAuthError, McpUnreachableError


def server(requests: list[httpx.Request], *, sse: bool = False) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        method = body["method"]
        if method == "notifications/initialized":
            return httpx.Response(202)
        result: dict[str, object] = {}
        headers: dict[str, str] = {}
        if method == "initialize":
            headers["mcp-session-id"] = "sess-1"
        if method == "tools/call":
            result = {"content": [{"type": "text", "text": "page text"}], "isError": False}
        message = {"jsonrpc": "2.0", "id": body["id"], "result": result}
        if sse:
            headers["content-type"] = "text/event-stream"
            return httpx.Response(
                200, headers=headers, text=f"event: message\ndata: {json.dumps(message)}\n\n"
            )
        return httpx.Response(200, headers=headers, json=message)

    return httpx.MockTransport(handle)


@pytest.mark.parametrize("sse", [False, True])
def test_call_tool_initializes_once_and_sends_access_headers(sse: bool) -> None:
    requests: list[httpx.Request] = []
    session = HttpMcpSession(
        "https://a1.example/mcp", "id-1", "secret-1", transport=server(requests, sse=sse)
    )
    assert session.call_tool("browser_snapshot", {}).text == "page text"
    assert session.call_tool("browser_snapshot", {}).text == "page text"
    methods = [json.loads(r.content)["method"] for r in requests]
    assert methods == ["initialize", "notifications/initialized", "tools/call", "tools/call"]
    assert all(r.headers["cf-access-client-id"] == "id-1" for r in requests)
    assert all(r.headers["cf-access-client-secret"] == "secret-1" for r in requests)
    assert requests[-1].headers["mcp-session-id"] == "sess-1"


@pytest.mark.parametrize("status", [401, 403])
def test_access_refusal_is_an_auth_error(status: int) -> None:
    session = HttpMcpSession(
        "https://a1.example/mcp",
        "i",
        "s",
        transport=httpx.MockTransport(lambda r: httpx.Response(status)),
    )
    with pytest.raises(McpAuthError):
        session.call_tool("browser_snapshot", {})


def test_server_errors_and_network_errors_are_unreachable_without_the_url() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("cannot reach https://a1.example/mcp")

    for transport in (
        httpx.MockTransport(lambda r: httpx.Response(502)),
        httpx.MockTransport(boom),
    ):
        session = HttpMcpSession("https://a1.example/mcp", "i", "s", transport=transport)
        with pytest.raises(McpUnreachableError) as info:
            session.call_tool("browser_snapshot", {})
        assert "a1.example" not in str(info.value)
