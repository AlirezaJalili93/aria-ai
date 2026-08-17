from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

WORKER_STAGING_REQUIRED_SETTINGS = (
    "database_url",
    "queue_broker_url",
    "storage_endpoint",
    "storage_bucket",
    "storage_access_key",
    "storage_secret_key",
    "auth_provider_url",
    "release_commit_sha",
)


class WorkerSettings(BaseSettings):
    app_env: Literal["local", "test", "staging", "production"]
    app_version: str
    log_level: str
    database_url: str | None = None
    queue_broker_url: str | None = None
    storage_endpoint: str | None = None
    storage_bucket: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: str | None = None
    auth_provider_url: str | None = None
    release_commit_sha: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_hosted_environment(self) -> Self:
        if self.app_env not in {"staging", "production"}:
            return self

        missing = [
            setting
            for setting in WORKER_STAGING_REQUIRED_SETTINGS
            if not (value := getattr(self, setting)) or not value.strip()
        ]
        if missing:
            raise ValueError(
                "Missing required hosted worker configuration: " + ", ".join(sorted(missing))
            )
        return self


def load_worker_settings() -> WorkerSettings:
    return WorkerSettings()  # type: ignore[call-arg]
