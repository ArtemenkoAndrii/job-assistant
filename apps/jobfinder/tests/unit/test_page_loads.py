"""Daily page-load counter (NFR-B5)."""

from datetime import UTC, datetime, timedelta

from jobfinder.storage.page_loads import InMemoryPageLoadCounter

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


def test_counts_up_to_the_limit_then_refuses() -> None:
    counter = InMemoryPageLoadCounter()
    assert all(counter.increment_if_below("linkedin", NOW, limit=3) for _ in range(3))
    assert not counter.increment_if_below("linkedin", NOW, limit=3)


def test_new_day_and_other_board_start_at_zero() -> None:
    counter = InMemoryPageLoadCounter()
    assert counter.increment_if_below("linkedin", NOW, limit=1)
    assert counter.increment_if_below("linkedin", NOW + timedelta(days=1), limit=1)
    assert counter.increment_if_below("glassdoor", NOW, limit=1)
