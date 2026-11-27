"""NFR-S1: every route except /health requires authentication."""

from typing import Any

from fastapi.testclient import TestClient

from jobfinder import __version__
from tests.conftest import HOST


def _leaves(routes: Any) -> list[Any]:
    """Every leaf route, descending into included routers."""
    leaves: list[Any] = []
    for route in routes:
        router = getattr(route, "original_router", None)
        leaves.extend(_leaves(router.routes) if router is not None else [route])
    return leaves


def _paths(app: Any) -> tuple[set[str], set[str]]:
    """(paths registered outside any router, paths on included routers)."""
    direct: set[str] = set()
    included: set[str] = set()
    for route in app.routes:
        router = getattr(route, "original_router", None)
        if router is not None:
            included |= {r.path for r in _leaves(router.routes)}
        else:
            direct.add(route.path)
    return direct, included


def _methods(app: Any) -> dict[str, set[str]]:
    """Methods per path on the protected routers."""
    methods: dict[str, set[str]] = {}
    for route in app.routes:
        router = getattr(route, "original_router", None)
        if router is not None:
            for r in _leaves(router.routes):
                methods.setdefault(r.path, set()).update(r.methods - {"HEAD", "OPTIONS"})
    return methods


def test_only_health_is_registered_outside_the_protected_router(client: TestClient) -> None:
    direct, included = _paths(client.app)
    assert direct == {"/health"}
    expected = {"/", "/profiles", "/settings", "/runs", "/static/app.css", "/static/htmx.min.js"}
    assert expected | {"/checks", "/checks/a1", "/checks/email"} <= included


def test_every_route_but_health_requires_auth(client: TestClient) -> None:
    for path, methods in _methods(client.app).items():
        for method in methods:
            response = client.request(method, path, headers={"origin": f"https://{HOST}"})
            assert response.status_code == 401, (method, path)


def test_health_is_open_and_minimal(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_docs_and_schema_are_not_exposed(client: TestClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path
