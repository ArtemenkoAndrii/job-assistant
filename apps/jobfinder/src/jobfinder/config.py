"""Settings from the environment. Secrets come from the secret manager at deploy time (#16)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JOBFINDER_")

    environment: str = "dev"


def get_settings() -> Settings:
    return Settings()
