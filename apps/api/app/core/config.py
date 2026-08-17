from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    app_env: Literal["local", "test", "staging", "production"]
    app_version: str
    log_level: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def load_api_settings() -> ApiSettings:
    # Required values are supplied by the environment at runtime; mypy cannot model BaseSettings IO.
    return ApiSettings()  # type: ignore[call-arg]
