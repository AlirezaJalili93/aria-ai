import pytest
from pydantic import ValidationError

from app.core.config import ApiSettings
from app.main import create_app


def test_create_app_uses_explicit_bootstrap_settings() -> None:
    settings = ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO")

    app = create_app(settings)

    assert app.title == "Aria API"
    assert app.version == "0.1.0"
    assert app.docs_url is None
    assert app.openapi_url is None


def test_bootstrap_exposes_no_undocumented_product_route() -> None:
    settings = ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO")

    app = create_app(settings)

    assert app.routes == []


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
        auth_provider_url="https://auth-staging.example.test",
        auth_jwks_url="https://auth-staging.example.test/.well-known/jwks.json",
        auth_audience="authenticated",
        release_commit_sha="0123456789abcdef",
    )

    assert settings.app_env == "staging"
    assert settings.storage_bucket == "aria-staging-artifacts"
