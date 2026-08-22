from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
CommitSha = Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F]{40}$")]
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _validated_postgres_secret(value: SecretStr) -> SecretStr:
    raw_value = value.get_secret_value()
    try:
        TypeAdapter(PostgresDsn).validate_python(raw_value)
    except ValidationError:
        raise ValueError("DATABASE_URL must be a valid PostgreSQL DSN") from None
    if urlsplit(raw_value).scheme not in {"postgres", "postgresql", "postgresql+asyncpg"}:
        raise ValueError("DATABASE_URL must use the supported async PostgreSQL scheme")
    return value


def _validated_redis_secret(value: SecretStr) -> SecretStr:
    raw_value = value.get_secret_value()
    try:
        TypeAdapter(RedisDsn).validate_python(raw_value)
    except ValidationError:
        raise ValueError("QUEUE_BROKER_URL must be a valid Redis-compatible DSN") from None
    parsed = urlsplit(raw_value)
    database = parsed.path.removeprefix("/")
    if parsed.scheme not in {"redis", "rediss"} or parsed.hostname is None:
        raise ValueError("QUEUE_BROKER_URL must use a supported Redis-compatible scheme")
    if database and not database.isdigit():
        raise ValueError("QUEUE_BROKER_URL database must be numeric")
    return value


PostgresSecret = Annotated[SecretStr, AfterValidator(_validated_postgres_secret)]
RedisSecret = Annotated[SecretStr, AfterValidator(_validated_redis_secret)]

WORKER_STAGING_REQUIRED_SETTINGS = (
    "database_url",
    "queue_broker_url",
    "storage_endpoint",
    "storage_bucket",
    "storage_access_key",
    "storage_secret_key",
    "release_commit_sha",
)


class WorkerSettings(BaseSettings):
    app_env: Literal["local", "test", "staging", "production"]
    app_version: NonEmptyString
    log_level: LogLevel
    database_url: PostgresSecret | None = None
    queue_broker_url: RedisSecret | None = None
    storage_endpoint: AnyHttpUrl | None = None
    storage_bucket: NonEmptyString | None = None
    storage_access_key: SecretStr | None = None
    storage_secret_key: SecretStr | None = None
    release_commit_sha: CommitSha | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    @model_validator(mode="after")
    def validate_hosted_environment(self) -> Self:
        if self.app_env not in {"staging", "production"}:
            return self

        missing = [
            setting
            for setting in WORKER_STAGING_REQUIRED_SETTINGS
            if getattr(self, setting) is None
        ]
        if missing:
            raise ValueError(
                "Missing required hosted worker configuration: " + ", ".join(sorted(missing))
            )
        return self


def load_worker_settings() -> WorkerSettings:
    return WorkerSettings()  # type: ignore[call-arg]
