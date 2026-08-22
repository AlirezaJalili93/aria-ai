from app.infrastructure.db.readiness import normalize_async_database_url


def test_normalize_async_database_url_adapts_standard_postgres_scheme() -> None:
    credentials = ":".join(("user", "placeholder"))
    database_url = f"postgresql://{credentials}@db.example.test/app"
    expected_url = f"postgresql+asyncpg://{credentials}@db.example.test/app"

    assert normalize_async_database_url(database_url) == expected_url


def test_normalize_async_database_url_preserves_asyncpg_scheme() -> None:
    credentials = ":".join(("user", "placeholder"))
    database_url = f"postgresql+asyncpg://{credentials}@db.example.test/app"

    assert normalize_async_database_url(database_url) == database_url


def test_normalize_async_database_url_adapts_postgres_alias() -> None:
    assert (
        normalize_async_database_url("postgres://db.example.test/app")
        == "postgresql+asyncpg://db.example.test/app"
    )
