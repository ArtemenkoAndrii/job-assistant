"""The card on a phone and the vendored htmx (spec AC17, AC22)."""

import re
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from jobfinder.web.app import HTMX, STYLESHEET


def test_htmx_is_vendored_pinned_and_served_behind_auth(
    client: TestClient, owner_headers: Any
) -> None:
    assert HTMX.read_text().startswith("/* htmx 2.0.4")
    assert client.get("/static/htmx.min.js").status_code == 401
    response = client.get("/static/htmx.min.js", headers=owner_headers)
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]


def test_pages_load_scripts_only_from_the_app(client: TestClient, owner_headers: Any) -> None:
    for path in ("/settings", "/profiles", "/runs"):
        html = client.get(path, headers=owner_headers).text
        sources = re.findall(r'<script[^>]*src="([^"]+)"', html)
        assert sources == ["/static/htmx.min.js"]
        assert not re.search(r'(?:src|href)="https?://', html)


def test_buttons_are_labelled_full_width_and_tall_enough() -> None:
    css = Path(STYLESHEET).read_text()
    button = re.search(r"\.button \{([^}]*)\}", css)
    assert button
    rules = button.group(1)
    assert "min-height: 44px" in rules
    assert "width: 100%" in rules  # one column on a phone
    assert re.search(r"\.button:focus-visible", css)
    assert "grid-template-columns: 1fr 1fr" in css  # two columns from 48rem


def test_status_is_text_and_announced(client: TestClient, owner_headers: Any) -> None:
    html = client.get("/settings", headers=owner_headers).text
    assert html.count('role="status" aria-live="polite"') == 2
    assert "Not run yet." in html
