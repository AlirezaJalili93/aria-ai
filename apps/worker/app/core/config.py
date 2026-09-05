from dataclasses import dataclass
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    Field,
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
PositiveInteger = Annotated[int, Field(gt=0)]


@dataclass(frozen=True, slots=True)
class QueueRuntimeConfiguration:
    broker_url: SecretStr
    queue_name: str
    visibility_timeout_seconds: int
    concurrency: int


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
    "queue_name",
    "queue_visibility_timeout_seconds",
    "worker_concurrency",
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
    queue_name: NonEmptyString | None = None
    queue_visibility_timeout_seconds: PositiveInteger | None = None
    worker_concurrency: PositiveInteger | None = None
    storage_endpoint: AnyHttpUrl | None = None
    storage_bucket: NonEmptyString | None = None
    storage_access_key: SecretStr | None = None
    storage_secret_key: SecretStr | None = None
    release_commit_sha: CommitSha | None = None
    railway_git_commit_sha: CommitSha | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    @model_validator(mode="after")
    def resolve_platform_commit_sha(self) -> Self:
        if self.railway_git_commit_sha is not None:
            self.release_commit_sha = self.railway_git_commit_sha
        return self

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

    def require_queue_runtime_configuration(self) -> QueueRuntimeConfiguration:
        required = (
            "queue_broker_url",
            "queue_name",
            "queue_visibility_timeout_seconds",
            "worker_concurrency",
        )
        missing = [setting for setting in required if getattr(self, setting) is None]
        if missing:
            raise ValueError(
                "Missing required Worker Queue runtime configuration: " + ", ".join(sorted(missing))
            )

        assert self.queue_broker_url is not None
        assert self.queue_name is not None
        assert self.queue_visibility_timeout_seconds is not None
        assert self.worker_concurrency is not None
        return QueueRuntimeConfiguration(
            broker_url=self.queue_broker_url,
            queue_name=self.queue_name,
            visibility_timeout_seconds=self.queue_visibility_timeout_seconds,
            concurrency=self.worker_concurrency,
        )


def load_worker_settings() -> WorkerSettings:
    return WorkerSettings()  # type: ignore[call-arg]
