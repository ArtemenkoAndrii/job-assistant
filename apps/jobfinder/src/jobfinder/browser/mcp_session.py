"""The MCP session to A-1 (Playwright MCP behind Cloudflare Access), spoken over Streamable HTTP.

A small synchronous client: `initialize`, `notifications/initialized`, `tools/call`. Only
`BrowserGateway` uses it (ADR-0011, NFR-M2). Error messages never carry the URL or the token.
"""

import json
from dataclasses import dataclass
from typing import Any, Protocol, Self

import httpx

TIMEOUT_SECONDS = 60.0
PROTOCOL_VERSION = "2025-03-26"
SESSION_HEADER = "mcp-session-id"


class McpAuthError(Exception):
    """Cloudflare Access (or the MCP host) refused the service token."""


class McpUnreachableError(Exception):
    """A-1 did not answer, or answered with something that is not MCP."""


@dataclass(frozen=True)
class ToolResult:
    text: str
    is_error: bool = False


class McpSession(Protocol):
    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult: ...

    def close(self) -> None: ...


class HttpMcpSession:
    def __init__(
        self,
        url: str,
        client_id: str,
        client_secret: str,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = url
        self._headers = {
            "CF-Access-Client-Id": client_id,
            "CF-Access-Client-Secret": client_secret,
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        self._http = httpx.Client(transport=transport, timeout=TIMEOUT_SECONDS)
        self._next_id = 0
        self._started = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if not self._started:
            self._initialize()
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        parts: list[dict[str, Any]] = result.get("content") or []
        text = "\n".join(str(p.get("text", "")) for p in parts if p.get("type") == "text")
        return ToolResult(text=text, is_error=bool(result.get("isError")))

    def _initialize(self) -> None:
        self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "jobfinder", "version": "0"},
            },
        )
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._started = True

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._next_id += 1
        body = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        response = self._post(body)
        message = _parse(response, self._next_id)
        if "error" in message or "result" not in message:
            raise McpUnreachableError("MCP error")
        return dict(message["result"])

    def _post(self, body: dict[str, Any]) -> httpx.Response:
        try:
            response = self._http.post(self._url, json=body, headers=self._headers)
        except Exception as exc:  # the message of a library error can contain the URL
            raise McpUnreachableError(type(exc).__name__) from None
        if response.status_code in (401, 403):
            raise McpAuthError(f"HTTP {response.status_code}")
        if response.status_code >= 300:
            raise McpUnreachableError(f"HTTP {response.status_code}")
        session_id = response.headers.get(SESSION_HEADER)
        if session_id:
            self._headers[SESSION_HEADER] = session_id
        return response


def _parse(response: httpx.Response, request_id: int) -> dict[str, Any]:
    """The JSON-RPC message answering `request_id`, from a JSON or an event-stream body."""
    try:
        if "text/event-stream" in response.headers.get("content-type", ""):
            for line in response.text.splitlines():
                if line.startswith("data:"):
                    message = json.loads(line[5:].strip())
                    if message.get("id") == request_id:
                        return dict(message)
            raise McpUnreachableError("no answer in the event stream")
        return dict(response.json())
    except McpUnreachableError:
        raise
    except Exception:
        raise McpUnreachableError("malformed MCP answer") from None
