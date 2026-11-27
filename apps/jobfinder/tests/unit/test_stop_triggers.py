"""Stop triggers on recorded-style snippets, English and Spanish (spec AC11, NFR-B7)."""

import pytest

from jobfinder.browser.stop_triggers import evaluate
from jobfinder.domain.runs import Reason

JOBS = "https://www.linkedin.com/jobs/search/?keywords=x"


@pytest.mark.parametrize(
    ("url", "title", "text", "status", "expected"),
    [
        (JOBS, "Jobs", "- heading 'Software Engineer' ... 25 results", None, None),
        ("https://www.linkedin.com/authwall?trk=x", "Sign Up", "", None, Reason.LOGIN_WALL),
        ("https://www.linkedin.com/uas/login?x", "LinkedIn Login", "", None, Reason.LOGIN_WALL),
        (JOBS, "Jobs", "Sign in to view more jobs", None, Reason.LOGIN_WALL),
        (JOBS, "Jobs", "Inicia sesión para ver más empleos", None, Reason.LOGIN_WALL),
        (JOBS, "Join LinkedIn", "", None, Reason.LOGIN_WALL),
        (JOBS, "Just a moment...", "", None, Reason.CHALLENGE),
        (JOBS, "Jobs", "Verify you are human", None, Reason.CHALLENGE),
        (JOBS, "Jobs", "Verifica que eres humano", None, Reason.CHALLENGE),
        (JOBS, "Jobs", "iframe challenges.cloudflare.com", None, Reason.CHALLENGE),
        (JOBS, "Jobs", "We noticed unusual activity", None, Reason.CHALLENGE),
        (JOBS, "403 Forbidden", "", None, Reason.CHALLENGE),
        (JOBS, "Jobs", "", 429, Reason.CHALLENGE),
    ],
)
def test_evaluate(
    url: str, title: str, text: str, status: int | None, expected: Reason | None
) -> None:
    assert evaluate(url, title, text, status) == expected
