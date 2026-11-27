"""Structure of the shell and the empty pages (spec AC12-AC14)."""

import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from jobfinder.web.app import STYLESHEET

PAGES = ["/profiles", "/settings", "/runs"]


def test_root_redirects_to_profiles(client: TestClient, owner_headers: Any) -> None:
    response = client.get("/", headers=owner_headers)
    assert response.status_code == 302
    assert response.headers["location"] == "/profiles"


@pytest.mark.parametrize("path", PAGES)
def test_page_structure(client: TestClient, owner_headers: Any, path: str) -> None:
    html = client.get(path, headers=owner_headers).text
    assert '<html lang="en">' in html
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
    for landmark in ("<header", "<nav", "<main"):
        assert landmark in html
    assert 'href="/_gcp_iap/clear_login_cookie">Sign out</a>' in html
    assert html.count('aria-current="page"') == 1
    assert f'href="{path}" aria-current="page"' in html
    assert 'aria-label="Main"' in html
    assert re.findall(r"<script[^>]*>", html) == ['<script src="/static/htmx.min.js" defer>']


def test_links_have_text_labels(client: TestClient, owner_headers: Any) -> None:
    html = client.get("/profiles", headers=owner_headers).text
    for text in re.findall(r"<a [^>]*>(.*?)</a>", html):
        assert text.strip()


def test_stylesheet_rules() -> None:
    css = Path(STYLESHEET).read_text()
    assert "min-height: 44px" in css and "min-width: 44px" in css
    assert ":focus-visible" in css
    assert "@media (min-width: 48rem)" in css
    assert "font: 1rem" in css


def test_stylesheet_is_served_behind_auth(client: TestClient, owner_headers: Any) -> None:
    assert client.get("/static/app.css").status_code == 401
    response = client.get("/static/app.css", headers=owner_headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")


def test_refusal_pages_are_generic(client: TestClient, make_token: Any) -> None:
    from jobfinder.web.auth import IAP_HEADER
    from tests.conftest import OWNER

    unauthenticated = client.get("/profiles")
    forbidden = client.get("/profiles", headers={IAP_HEADER: make_token("someone@example.test")})
    assert (unauthenticated.status_code, forbidden.status_code) == (401, 403)
    for response in (unauthenticated, forbidden):
        assert "can't open this page" in response.text
        assert OWNER not in response.text
        assert "someone@example.test" not in response.text
