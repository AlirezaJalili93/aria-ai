from fastapi import FastAPI

from app.core.config import ApiSettings, load_api_settings


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    resolved_settings = settings or load_api_settings()
    return FastAPI(
        title="Aria API",
        version=resolved_settings.app_version,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
