from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from test_preview_access import setup_access

from app.infrastructure.db.preview_access import PostgresPreviewCapabilityResolver


def setup_resolver():
    _, _, _, auth, *_ = setup_access()
    binding = auth.binding
    value = {
        name: str(getattr(binding, name))
        for name in (
            "account_id",
            "project_id",
            "artifact_id",
            "artifact_version_id",
            "representation_id",
        )
    }
    value.update(
        version_no=binding.version_no,
        source_hash=binding.source_hash,
        source_ref=binding.source_ref,
        manifest_ref=auth.manifest_ref,
        manifest_hash=auth.manifest_hash,
    )
    connection = MagicMock()
    connection.scalar = AsyncMock(return_value=value)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=connection)
    context.__aexit__ = AsyncMock(return_value=False)
    engine = MagicMock()
    engine.begin.return_value = context
    return PostgresPreviewCapabilityResolver(engine), connection, context, value, auth


def test_only_hash_goes_to_fixed_resolve_helper_and_transaction_closes_before_return():
    resolver, connection, context, _, auth = setup_resolver()
    assert asyncio.run(resolver.resolve("a" * 64)) == auth
    sql, parameters = connection.scalar.call_args.args
    assert str(sql) == "SELECT aria_internal.resolve_preview(:token_hash)"
    assert parameters == {"token_hash": "a" * 64}
    context.__aexit__.assert_awaited_once()


@pytest.mark.parametrize("value", ["", "a" * 63, "A" * 64, "secret/token"])
def test_malformed_hash_never_reaches_database(value):
    resolver, connection, *_ = setup_resolver()
    assert asyncio.run(resolver.resolve(value)) is None
    connection.scalar.assert_not_awaited()


@pytest.mark.parametrize("change", ["none", "extra", "bool", "identity", "hash", "error"])
def test_invalid_helper_output_and_database_failure_are_not_access(change):
    resolver, connection, _, value, _ = setup_resolver()
    if change == "none":
        connection.scalar.return_value = None
    elif change == "extra":
        value["token"] = "prohibited"
    elif change == "bool":
        value["version_no"] = True
    elif change == "identity":
        value["account_id"] = "bad"
    elif change == "hash":
        value["manifest_hash"] = "prohibited"
    else:
        connection.scalar.side_effect = SQLAlchemyError("prohibited diagnostic")
    assert asyncio.run(resolver.resolve("a" * 64)) is None
