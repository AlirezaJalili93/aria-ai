from collections.abc import Awaitable, Callable

from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app

FULL_COMMIT_SHA = "0123456789abcdef0123456789abcdef01234567"


class StubDatabaseProbe:
    def __init__(self, result: bool) -> None:
        self._result = result
        self.calls = 0

    async def __call__(self) -> bool:
        self.calls += 1
        return self._result


def create_test_client(
    database_probe: Callable[[], Awaitable[bool]],
    queue_probe: Callable[[], Awaitable[bool]],
) -> TestClient:
    settings = ApiSettings(
        app_env="test",
        app_version="0.1.0",
        log_level="INFO",
        release_commit_sha=FULL_COMMIT_SHA,
    )
    return TestClient(
        create_app(settings, database_probe=database_probe, queue_probe=queue_probe)
    )


def test_liveness_reports_process_metadata_without_calling_dependencies() -> None:
    database_probe = StubDatabaseProbe(result=False)
    queue_probe = StubDatabaseProbe(result=False)

    response = create_test_client(database_probe, queue_probe).get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "alive",
        "service": "aria-api",
        "environment": "test",
        "version": "0.1.0",
        "release_commit_sha": FULL_COMMIT_SHA,
    }
    assert database_probe.calls == 0
    assert queue_probe.calls == 0


def test_readiness_reports_ready_when_configuration_and_database_are_available() -> None:
    database_probe = StubDatabaseProbe(result=True)
    queue_probe = StubDatabaseProbe(result=True)

    response = create_test_client(database_probe, queue_probe).get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "aria-api",
        "environment": "test",
        "version": "0.1.0",
        "release_commit_sha": FULL_COMMIT_SHA,
        "checks": {"configuration": "pass", "database": "pass", "queue": "pass"},
    }
    assert database_probe.calls == 1
    assert queue_probe.calls == 1


def test_readiness_returns_sanitized_503_when_database_is_unavailable() -> None:
    database_probe = StubDatabaseProbe(result=False)
    queue_probe = StubDatabaseProbe(result=True)

    response = create_test_client(database_probe, queue_probe).get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "service": "aria-api",
        "environment": "test",
        "version": "0.1.0",
        "release_commit_sha": FULL_COMMIT_SHA,
        "checks": {"configuration": "pass", "database": "fail", "queue": "pass"},
    }
    assert "database_url" not in response.text.lower()
    assert "provider" not in response.text.lower()
    assert database_probe.calls == 1
    assert queue_probe.calls == 1


def test_readiness_returns_sanitized_503_when_queue_is_unavailable() -> None:
    database_probe = StubDatabaseProbe(result=True)
    queue_probe = StubDatabaseProbe(result=False)

    response = create_test_client(database_probe, queue_probe).get("/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"] == {
        "configuration": "pass",
        "database": "pass",
        "queue": "fail",
    }
    assert "queue_broker_url" not in response.text.lower()
    assert database_probe.calls == 1
    assert queue_probe.calls == 1
