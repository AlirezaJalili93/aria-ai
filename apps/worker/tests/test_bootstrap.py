import json

import pytest
from pydantic import ValidationError

from app.core.config import WorkerSettings
from app.main import bootstrap_worker, run_worker

FULL_COMMIT_SHA = "0123456789abcdef0123456789abcdef01234567"


def test_bootstrap_worker_remains_queue_neutral() -> None:
    settings = WorkerSettings(app_env="test", app_version="0.1.0", log_level="INFO")

    worker = bootstrap_worker(settings)

    assert worker.service_name == "aria-worker"
    assert worker.queue_adapter_configured is False
    assert worker.environment == "test"


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
        storage_endpoint="https://storage-staging.example.test",
        storage_bucket="aria-staging-artifacts",
        storage_access_key="test-access-key",
        storage_secret_key="test-secret-key",
        release_commit_sha=FULL_COMMIT_SHA,
    )

    worker = bootstrap_worker(settings)

    assert worker.environment == "staging"
    assert worker.app_version == "0.1.0"
    assert not hasattr(settings, "auth_provider_url")
    assert "test-secret-key" not in repr(settings)
    assert "postgresql://staging.example.test/aria" not in repr(settings)


def test_worker_runtime_stays_alive_after_successful_bootstrap(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = WorkerSettings(app_env="test", app_version="0.1.0", log_level="INFO")
    wait_calls = 0

    def record_wait() -> None:
        nonlocal wait_calls
        wait_calls += 1

    run_worker(settings, wait=record_wait)

    assert wait_calls == 1
    event = json.loads(capsys.readouterr().out)
    assert event["event_name"] == "worker.runtime_started"
    assert event["service"] == "aria-worker"
    assert event["queue_adapter_configured"] is False
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
