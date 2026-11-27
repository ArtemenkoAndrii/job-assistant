from collections.abc import Callable
from typing import Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from jobfinder.config import Settings
from jobfinder.web.csrf import check_origin
from tests.conftest import HOST

HASH_HOST = "jobfinder-web-abcdef-uc.a.run.app"


@pytest.fixture
def post_client() -> Callable[[str, str], TestClient]:
    """A test app with one POST route behind the Origin check (the real app has none yet)."""

    def make(environment: str, host: str) -> TestClient:
        app = FastAPI()
        app.state.settings = Settings(environment=environment)

        @app.post("/x", dependencies=[Depends(check_origin)])
        def post() -> dict[str, str]:
            return {"ok": "yes"}

        return TestClient(app, base_url=f"https://{host}")

    return make


@pytest.mark.parametrize("host", [HOST, HASH_HOST])
def test_matching_origin_passes_on_either_url(
    post_client: Callable[[str, str], TestClient], host: str
) -> None:
    client = post_client("production", host)
    assert client.post("/x", headers={"origin": f"https://{host}"}).status_code == 200
    assert client.post("/x", headers={"origin": f"https://{host.upper()}"}).status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {"origin": "https://evil.test"},
        {"origin": f"https://{HOST}.evil.test"},
        {"origin": "null"},
        {},
        {"origin": "https://evil.test", "x-forwarded-host": "evil.test"},
    ],
)
def test_foreign_or_missing_origin_is_403(
    post_client: Callable[[str, str], TestClient], headers: dict[str, str]
) -> None:
    assert post_client("production", HOST).post("/x", headers=headers).status_code == 403


def test_origin_matching_only_forwarded_host_is_refused(
    post_client: Callable[[str, str], TestClient],
) -> None:
    headers = {"origin": "https://other.test", "x-forwarded-host": "other.test"}
    assert post_client("production", HOST).post("/x", headers=headers).status_code == 403


def test_http_origin_only_in_dev(post_client: Callable[[str, str], TestClient]) -> None:
    headers = {"origin": f"http://{HOST}"}
    assert post_client("dev", HOST).post("/x", headers=headers).status_code == 200
    assert post_client("production", HOST).post("/x", headers=headers).status_code == 403


def test_safe_methods_need_no_origin(client: TestClient) -> None:
    assert client.get("/health").status_code == 200


def test_unauthenticated_post_with_foreign_origin_is_403(client: TestClient) -> None:
    """Origin runs before auth; the app has no POST route, so use a real path with a bad method
    is 405. Mount a POST on the real app's router for this check."""
    app: Any = client.app
    from fastapi import APIRouter

    from jobfinder.web.app import authenticate

    router = APIRouter(dependencies=[Depends(check_origin), Depends(authenticate)])

    @router.post("/probe")
    def probe() -> dict[str, str]:
        return {"ok": "yes"}

    app.include_router(router)
    assert client.post("/probe", headers={"origin": "https://evil.test"}).status_code == 403
    assert client.post("/probe", headers={"origin": f"https://{HOST}"}).status_code == 401
