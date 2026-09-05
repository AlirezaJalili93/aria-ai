import json

import pytest
from pydantic import ValidationError

from app.core.config import WorkerSettings
from app.main import bootstrap_worker, run_worker

FULL_COMMIT_SHA = "0123456789abcdef0123456789abcdef01234567"
STALE_COMMIT_SHA = "89abcdef0123456789abcdef0123456789abcdef"


class RuntimeProbe:
    def __init__(self) -> None:
        self.run_calls = 0

    def run(self) -> None:
        self.run_calls += 1


def queue_settings() -> WorkerSettings:
    return WorkerSettings(
        app_env="test",
        app_version="0.1.0",
        log_level="INFO",
        queue_broker_url="redis://queue.test:6379/0",
        queue_name="aria-test-jobs",
        queue_visibility_timeout_seconds=60,
        worker_concurrency=1,
    )


def test_bootstrap_worker_reports_configured_queue_adapter() -> None:
    settings = queue_settings()

    worker = bootstrap_worker(settings)

    assert worker.service_name == "aria-worker"
    assert worker.queue_adapter_configured is True
    assert worker.environment == "test"


def test_worker_runtime_fails_closed_without_explicit_queue_configuration() -> None:
    settings = WorkerSettings(app_env="test", app_version="0.1.0", log_level="INFO")

    with pytest.raises(ValueError, match="Missing required Worker Queue runtime configuration"):
        run_worker(settings, queue_runtime=RuntimeProbe())


def test_staging_worker_settings_fail_fast_without_service_bindings() -> None:
    with pytest.raises(ValidationError, match="Missing required hosted worker configuration"):
        WorkerSettings(app_env="staging", app_version="0.1.0", log_level="INFO")


def test_staging_worker_settings_accept_documented_service_bindings() -> None:
    settings = WorkerSettings(
        app_env="staging",
        app_version="0.1.0",
        log_level="INFO",
        database_url="postgresql://staging.example.test/aria",
        queue_broker_url="redis://queue-staging.example.test:6379/0",
        queue_name="aria-staging-jobs",
        queue_visibility_timeout_seconds=60,
        worker_concurrency=1,
        storage_endpoint="https://storage-staging.example.test",
        storage_bucket="aria-staging-artifacts",
        storage_access_key="test-access-key",
        storage_secret_key="test-secret-key",
        railway_git_commit_sha=FULL_COMMIT_SHA,
    )

    worker = bootstrap_worker(settings)

    assert worker.environment == "staging"
    assert worker.app_version == "0.1.0"
    assert settings.release_commit_sha == FULL_COMMIT_SHA
    assert not hasattr(settings, "auth_provider_url")
    assert "test-secret-key" not in repr(settings)
    assert "postgresql://staging.example.test/aria" not in repr(settings)


def test_railway_git_commit_sha_is_the_worker_runtime_source_of_truth() -> None:
    settings = WorkerSettings(
        app_env="test",
        app_version="0.1.0",
        log_level="INFO",
        release_commit_sha=STALE_COMMIT_SHA,
        railway_git_commit_sha=FULL_COMMIT_SHA,
    )

    assert settings.release_commit_sha == FULL_COMMIT_SHA


def test_worker_runtime_stays_alive_after_successful_bootstrap(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = queue_settings()
    runtime = RuntimeProbe()

    run_worker(settings, queue_runtime=runtime)

    assert runtime.run_calls == 1
    event = json.loads(capsys.readouterr().out)
    assert event["event_name"] == "worker.runtime_started"
    assert event["service"] == "aria-worker"
    assert event["queue_adapter_configured"] is True
    assert event["status"] == "started"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("database_url", "hello"),
        ("database_url", "postgresql+psycopg://staging.example.test/aria"),
        ("queue_broker_url", "123"),
        ("queue_broker_url", "redis://queue-staging.example.test/not-a-number"),
        ("storage_endpoint", "not-a-url"),
        ("release_commit_sha", "abc"),
        ("railway_git_commit_sha", "abc"),
        ("log_level", "BLABLA"),
    ],
)
def test_worker_rejects_invalid_typed_values_without_leaking_input(
    field: str,
    value: str,
) -> None:
    values = {
        "app_env": "staging",
        "app_version": "0.1.0",
        "log_level": "INFO",
        "database_url": "postgresql://staging.example.test/aria",
        "queue_broker_url": "redis://queue-staging.example.test:6379/0",
        "queue_name": "aria-staging-jobs",
        "queue_visibility_timeout_seconds": 60,
        "worker_concurrency": 1,
        "storage_endpoint": "https://storage-staging.example.test",
        "storage_bucket": "aria-staging-artifacts",
        "storage_access_key": "test-access-key",
        "storage_secret_key": "test-secret-key",
        "release_commit_sha": FULL_COMMIT_SHA,
    }
    values[field] = value

    with pytest.raises(ValidationError) as error:
        WorkerSettings(**values)  # type: ignore[arg-type]

    assert value not in str(error.value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("queue_name", " "),
        ("queue_visibility_timeout_seconds", 0),
        ("worker_concurrency", 0),
    ],
)
def test_worker_rejects_invalid_queue_runtime_values(field: str, value: object) -> None:
    values = {
        "app_env": "staging",
        "app_version": "0.1.0",
        "log_level": "INFO",
        "database_url": "postgresql://staging.example.test/aria",
        "queue_broker_url": "redis://queue-staging.example.test:6379/0",
        "queue_name": "aria-staging-jobs",
        "queue_visibility_timeout_seconds": 60,
        "worker_concurrency": 1,
        "storage_endpoint": "https://storage-staging.example.test",
        "storage_bucket": "aria-staging-artifacts",
        "storage_access_key": "test-access-key",
        "storage_secret_key": "test-secret-key",
        "release_commit_sha": FULL_COMMIT_SHA,
    }
    values[field] = value

    with pytest.raises(ValidationError):
        WorkerSettings(**values)  # type: ignore[arg-type]
