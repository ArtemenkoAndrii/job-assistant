"""BrowserGateway with a fake MCP session (spec AC9-AC13)."""

from datetime import UTC, datetime
from typing import Any

import pytest

from jobfinder.browser.gateway import BrowserBlockedError, BrowserGateway, search_url
from jobfinder.browser.mcp_session import McpAuthError, McpUnreachableError, ToolResult
from jobfinder.domain.runs import Reason
from jobfinder.storage.page_loads import InMemoryPageLoadCounter

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
URL = search_url()


def page(url: str = URL, title: str = "Jobs", body: str = "") -> ToolResult:
    text = f"### Page state\n- Page URL: {url}\n- Page Title: {title}\n{body}"
    return ToolResult(text)


RESULTS = page(body="- list 'Search results': " + "- listitem 'Software Engineer at Acme' " * 10)


class FakeSession:
    def __init__(self, *results: ToolResult | Exception) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        self.calls.append((name, arguments))
        item = self.results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self) -> None:
        pass


def gateway(
    session: FakeSession,
    counter: InMemoryPageLoadCounter | None = None,
    pauses: list[float] | None = None,
) -> BrowserGateway:
    log = pauses if pauses is not None else []
    return BrowserGateway(
        session,
        counter or InMemoryPageLoadCounter(),
        sleep=log.append,
        uniform=lambda a, b: 2.5,
        clock=lambda: NOW,
    )


def test_normal_page_succeeds_with_counter_and_pause() -> None:
    session = FakeSession(page(), RESULTS)
    counter = InMemoryPageLoadCounter()
    pauses: list[float] = []
    chars = gateway(session, counter, pauses).check_search_page()
    assert chars == len(RESULTS.text) > 100
    assert counter.counts == {"linkedin-20261127": 1}
    assert pauses == [2.5]


def test_only_navigate_and_snapshot_are_called() -> None:
    session = FakeSession(page(), RESULTS)
    gateway(session).check_search_page()
    assert [name for name, _ in session.calls] == ["browser_navigate", "browser_snapshot"]
    assert session.calls[0][1] == {"url": URL}
    assert session.calls[1][1] == {}
    assert all("filename" not in args for _, args in session.calls)


def test_search_url_is_https_linkedin_jobs() -> None:
    assert URL.startswith("https://www.linkedin.com/jobs/search/")


@pytest.mark.parametrize(
    ("first", "expected"),
    [
        (page("https://www.linkedin.com/authwall?x", "Sign Up"), Reason.LOGIN_WALL),
        (page(body="Sign in to view more jobs"), Reason.LOGIN_WALL),
        (page(title="Just a moment..."), Reason.CHALLENGE),
        (ToolResult("boom", is_error=True), Reason.A1_UNREACHABLE),
        (McpUnreachableError("HTTP 502"), Reason.A1_UNREACHABLE),
        (McpAuthError("HTTP 403"), Reason.A1_AUTH),
    ],
)
def test_blocks_after_the_first_result_and_asks_for_no_more(
    first: ToolResult | Exception, expected: Reason
) -> None:
    session = FakeSession(first, RESULTS)
    with pytest.raises(BrowserBlockedError) as info:
        gateway(session).check_search_page()
    assert info.value.reason == expected
    assert len(session.calls) == 1


def test_block_found_in_the_snapshot_stops_the_check() -> None:
    session = FakeSession(page(), page(title="Verify you are human"))
    with pytest.raises(BrowserBlockedError) as info:
        gateway(session).check_search_page()
    assert info.value.reason == Reason.CHALLENGE


def test_empty_snapshot_is_a_failure() -> None:
    session = FakeSession(page(), ToolResult(""))
    with pytest.raises(BrowserBlockedError) as info:
        gateway(session).check_search_page()
    assert info.value.reason == Reason.EMPTY_SNAPSHOT


def test_landing_on_another_host_is_off_policy() -> None:
    elsewhere = page("https://example.org/jobs/", body="x" * 200)
    session = FakeSession(page(), elsewhere)
    with pytest.raises(BrowserBlockedError) as info:
        gateway(session).check_search_page()
    assert info.value.reason == Reason.OFF_POLICY


def test_daily_limit_blocks_before_any_browser_call() -> None:
    counter = InMemoryPageLoadCounter()
    counter.counts["linkedin-20261127"] = 150
    session = FakeSession(page(), RESULTS)
    with pytest.raises(BrowserBlockedError) as info:
        gateway(session, counter).check_search_page()
    assert info.value.reason == Reason.DAILY_LIMIT
    assert session.calls == []
