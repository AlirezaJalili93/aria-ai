import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import ApiSettings
from app.infrastructure.auth.supabase_jwt import SupabaseJwtVerifier
from app.main import create_app

FULL_COMMIT_SHA = "0123456789abcdef0123456789abcdef01234567"
STALE_COMMIT_SHA = "89abcdef0123456789abcdef0123456789abcdef"


def test_create_app_uses_explicit_bootstrap_settings() -> None:
    settings = ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO")

    app = create_app(settings)

    assert app.title == "Aria API"
    assert app.version == "0.1.0"
    assert app.docs_url is None
    assert app.openapi_url is None


def test_bootstrap_and_project_routes_enforce_authentication() -> None:
    settings = ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO")

    app = create_app(settings)

    client = TestClient(app)

    assert client.get("/health/live").status_code == 200
    assert client.post("/api/v1/auth/bootstrap").status_code == 401
    assert client.get("/api/v1/projects").status_code == 401


def test_staging_settings_fail_fast_when_service_bindings_are_missing() -> None:
    with pytest.raises(ValidationError, match="Missing required hosted runtime configuration"):
        ApiSettings(app_env="staging", app_version="0.1.0", log_level="INFO")


def test_staging_settings_accept_the_documented_service_bindings() -> None:
    settings = ApiSettings(
        app_env="staging",
        app_version="0.1.0",
        log_level="INFO",
        public_app_url="https://staging.example.test",
        api_base_url="https://api-staging.example.test/api/v1",
        database_url="postgresql://staging.example.test/aria",
        queue_broker_url="redis://queue-staging.example.test:6379/0",
        storage_endpoint="https://storage-staging.example.test",
        storage_bucket="aria-staging-artifacts",
        storage_access_key="test-access-key",
        storage_secret_key="test-secret-key",
        auth_provider_url="https://auth-staging.example.test/auth/v1",
        auth_jwks_url="https://auth-staging.example.test/auth/v1/.well-known/jwks.json",
        auth_audience="authenticated",
        railway_git_commit_sha=FULL_COMMIT_SHA,
    )

    assert settings.app_env == "staging"
    assert settings.storage_bucket == "aria-staging-artifacts"
    assert settings.release_commit_sha == FULL_COMMIT_SHA
    assert "test-secret-key" not in repr(settings)
    assert "postgresql://staging.example.test/aria" not in repr(settings)

    app = create_app(settings)

    assert isinstance(app.state.access_token_verifier, SupabaseJwtVerifier)
    assert app.state.access_token_verifier._issuer == (  # noqa: SLF001 - wiring contract
        "https://auth-staging.example.test/auth/v1"
    )


def test_railway_git_commit_sha_is_the_runtime_source_of_truth() -> None:
    settings = ApiSettings(
        app_env="test",
        app_version="0.1.0",
        log_level="INFO",
        release_commit_sha=STALE_COMMIT_SHA,
        railway_git_commit_sha=FULL_COMMIT_SHA,
    )

    assert settings.release_commit_sha == FULL_COMMIT_SHA


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("public_app_url", "not-a-url"),
        ("api_base_url", "not-a-url"),
        ("database_url", "hello"),
        ("database_url", "postgresql+psycopg://staging.example.test/aria"),
        ("queue_broker_url", "123"),
        ("queue_broker_url", "redis://queue-staging.example.test/not-a-number"),
        ("storage_endpoint", "not-a-url"),
        ("auth_provider_url", "banana"),
        ("auth_jwks_url", "not-a-url"),
        ("release_commit_sha", "abc"),
        ("railway_git_commit_sha", "abc"),
        ("log_level", "BLABLA"),
    ],
)
def test_staging_settings_reject_malformed_typed_values(field: str, value: str) -> None:
    values = {
        "app_env": "staging",
        "app_version": "0.1.0",
        "log_level": "INFO",
        "public_app_url": "https://staging.example.test",
        "api_base_url": "https://api-staging.example.test/api/v1",
        "database_url": "postgresql://staging.example.test/aria",
        "queue_broker_url": "redis://queue-staging.example.test:6379/0",
        "storage_endpoint": "https://storage-staging.example.test",
        "storage_bucket": "aria-staging-artifacts",
        "storage_access_key": "test-access-key",
        "storage_secret_key": "test-secret-key",
        "auth_provider_url": "https://auth-staging.example.test/auth/v1",
        "auth_jwks_url": "https://auth-staging.example.test/auth/v1/.well-known/jwks.json",
        "auth_audience": "authenticated",
        "release_commit_sha": FULL_COMMIT_SHA,
    }
    values[field] = value

    with pytest.raises(ValidationError) as error:
        ApiSettings(**values)  # type: ignore[arg-type]

    assert value not in str(error.value)
