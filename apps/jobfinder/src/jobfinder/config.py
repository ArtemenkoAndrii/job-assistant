"""Settings from the environment. Secrets come from the secret manager at deploy time (#16).

The default environment is production. Local runs need `JOBFINDER_ENVIRONMENT=dev` (ADR-0008 §6);
the app refuses to start in `dev` on Cloud Run, where `K_SERVICE` is set.
"""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict

DEV = "dev"
PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JOBFINDER_")

    environment: str = PRODUCTION
    # From the Secret Manager value `owner-email`; empty means everyone is refused (ADR-0008).
    owner_email: str = ""
    project_number: str = ""
    region: str = "us-central1"
    service_name: str = "jobfinder-web"

    @property
    def is_dev(self) -> bool:
        return self.environment == DEV

    @property
    def iap_audience(self) -> str:
        return (
            f"/projects/{self.project_number}/locations/{self.region}/services/{self.service_name}"
        )


def get_settings() -> Settings:
    return Settings()


def check_startup(settings: Settings) -> None:
    """Refuse to start in `dev` on Cloud Run (ADR-0008 §6)."""
    if settings.is_dev and os.environ.get("K_SERVICE"):
        msg = "JOBFINDER_ENVIRONMENT=dev is not allowed on Cloud Run (K_SERVICE is set)"
        raise RuntimeError(msg)
