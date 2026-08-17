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

