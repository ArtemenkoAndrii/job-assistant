"""NFR-S1: every route except /health requires authentication."""

from typing import Any

from fastapi.testclient import TestClient

from jobfinder import __version__


def _paths(app: Any) -> tuple[set[str], set[str]]:
    """(paths registered outside any router, paths on included routers)."""
    direct: set[str] = set()
    included: set[str] = set()
    for route in app.routes:
        router = getattr(route, "original_router", None)
        if router is not None:
            included |= {r.path for r in router.routes}
        else:
            direct.add(route.path)
    return direct, included


def test_only_health_is_registered_outside_the_protected_router(client: TestClient) -> None:
    direct, included = _paths(client.app)
    assert direct == {"/health"}
    assert {"/", "/profiles", "/settings", "/runs", "/static/app.css"} <= included


def test_every_route_but_health_requires_auth(client: TestClient) -> None:
    _, included = _paths(client.app)
    for path in included:
        assert client.get(path).status_code == 401, path


def test_health_is_open_and_minimal(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_docs_and_schema_are_not_exposed(client: TestClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path
