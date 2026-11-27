"""BrowserGateway: the only path to A-1 (ADR-0011, NFR-M2).

For the skeleton check it exposes one operation: open a LinkedIn jobs search page that the gateway
builds itself, take one snapshot, and report how big it was. Rules are code, not instructions:
tool allowlist, https and host check, daily page-load limit, pause between actions, and stop
triggers after every result.
"""

import random
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import quote, urlsplit

from jobfinder.browser.mcp_session import (
    McpAuthError,
    McpSession,
    McpUnreachableError,
    ToolResult,
)
from jobfinder.browser.stop_triggers import evaluate
from jobfinder.domain.runs import Reason
from jobfinder.storage.page_loads import PageLoadCounter

BOARD = "linkedin"
SEARCH_KEYWORDS = (
    "software engineer"  # fixed and non-personal; no user or page input reaches the URL
)
SEARCH_HOST = "www.linkedin.com"
MIN_SNAPSHOT_CHARS = 100
PAUSE_RANGE = (1.0, 5.0)  # NFR-B6

_URL_LINE = re.compile(r"^\s*-?\s*Page URL:\s*(\S+)", re.MULTILINE)
_TITLE_LINE = re.compile(r"^\s*-?\s*Page Title:\s*(.*)$", re.MULTILINE)


class BrowserBlockedError(Exception):
    """The gateway stopped; `reason` says why. There is no retry."""

    def __init__(self, reason: Reason) -> None:
        super().__init__(reason.value)
        self.reason = reason


def search_url() -> str:
    """The jobs search URL, built from constants (ADR-0011 §3)."""
    return f"https://{SEARCH_HOST}/jobs/search/?keywords={quote(SEARCH_KEYWORDS)}&f_TPR=r604800"


class BrowserGateway:
    def __init__(
        self,
        session: McpSession,
        counter: PageLoadCounter,
        *,
        sleep: Callable[[float], None] = time.sleep,
        uniform: Callable[[float, float], float] = random.uniform,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session = session
        self._counter = counter
        self._sleep = sleep
        self._uniform = uniform
        self._clock = clock

    def check_search_page(self) -> int:
        """Open the search page and take one snapshot. Returns the snapshot's size in characters."""
        if not self._counter.increment_if_below(BOARD, self._clock()):
            raise BrowserBlockedError(Reason.DAILY_LIMIT)
        url = search_url()
        navigated = self._call("browser_navigate", {"url": url})
        self._inspect(navigated, fallback_url=url)
        self._sleep(self._uniform(*PAUSE_RANGE))
        snapshot = self._call("browser_snapshot", {})
        final_url = self._inspect(snapshot, fallback_url=url)
        if len(snapshot.text.strip()) < MIN_SNAPSHOT_CHARS:
            raise BrowserBlockedError(Reason.EMPTY_SNAPSHOT)
        self._check_policy(final_url)
        return len(snapshot.text)

    def _call(self, tool: str, arguments: dict[str, str]) -> ToolResult:
        try:
            result = self._session.call_tool(tool, arguments)
        except McpAuthError:
            raise BrowserBlockedError(Reason.A1_AUTH) from None
        except McpUnreachableError:
            raise BrowserBlockedError(Reason.A1_UNREACHABLE) from None
        if result.is_error:
            raise BrowserBlockedError(Reason.A1_UNREACHABLE)
        return result

    def _inspect(self, result: ToolResult, *, fallback_url: str) -> str:
        """Run the stop triggers over a result; returns the page URL it reports."""
        url_match = _URL_LINE.search(result.text)
        title_match = _TITLE_LINE.search(result.text)
        url = url_match.group(1) if url_match else fallback_url
        title = title_match.group(1) if title_match else ""
        reason = evaluate(url, title, result.text)
        if reason is not None:
            raise BrowserBlockedError(reason)
        return url

    @staticmethod
    def _check_policy(url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname != SEARCH_HOST:
            raise BrowserBlockedError(Reason.OFF_POLICY)
        if not parts.path.startswith("/jobs/"):
            raise BrowserBlockedError(Reason.OFF_POLICY)
