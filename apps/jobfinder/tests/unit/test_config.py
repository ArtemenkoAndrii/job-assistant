import pytest

from jobfinder.config import Settings, check_startup
from jobfinder.web.app import create_app


def test_default_environment_is_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JOBFINDER_ENVIRONMENT", raising=False)
    assert Settings().environment == "production"
    assert not Settings().is_dev


def test_dev_on_cloud_run_refuses_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("K_SERVICE", "jobfinder-web")
    with pytest.raises(RuntimeError):
        check_startup(Settings(environment="dev"))
    with pytest.raises(RuntimeError):
        create_app(Settings(environment="dev"))


def test_dev_locally_and_production_on_cloud_run_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("K_SERVICE", raising=False)
    check_startup(Settings(environment="dev"))
    monkeypatch.setenv("K_SERVICE", "jobfinder-web")
    check_startup(Settings(environment="production"))
