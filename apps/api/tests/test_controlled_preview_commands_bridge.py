"""Private test transport shape/diagnostics; no HTTP/identity-verifier claim."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from io import StringIO
from pathlib import Path

import pytest
from aria_backend_application.preview_delivery import PreviewError


def bridge():
    root = Path(__file__).parents[3]
    spec = importlib.util.spec_from_file_location(
        "controlled_preview_bridge", root / "tests/e2e/controlled_preview_commands_api.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"operation": "unknown"},
        {"operation": "publish", "role": "owner", "token": "synthetic-secret-marker"},
    ],
)
def test_bridge_rejects_invalid_shape_before_database_access(payload, monkeypatch):
    module = bridge()
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    with pytest.raises(PreviewError) as caught:
        asyncio.run(module.execute(payload))
    assert caught.value.code == "VALIDATION_FAILED"
    assert "synthetic-secret-marker" not in str(caught.value)


def test_bridge_rejects_nonlocal_or_nonowned_database_before_engine_creation(monkeypatch):
    module = bridge()
    payload = {
        "operation": "revoke",
        "subject_id": "x",
        "account_id": "x",
        "project_id": "x",
        "key": "key",
        "publication_id": "x",
    }
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+asyncpg://user@127.0.0.1/customer_database")
    with pytest.raises(PreviewError) as caught:
        asyncio.run(module.execute(payload))
    assert caught.value.code == "FEATURE_NOT_ENABLED"


def test_bridge_unknown_error_has_no_traceback_or_raw_error_in_response(monkeypatch, capsys):
    module = bridge()

    async def broken(value):
        raise RuntimeError("synthetic-private-error-marker")

    monkeypatch.setattr(module, "execute", broken)
    monkeypatch.setattr(module.sys, "stdin", StringIO("{}"))
    module.main()
    output = capsys.readouterr()
    assert not output.err
    assert json.loads(output.out) == {
        "status": "failed",
        "error_code": "PREVIEW_FINALIZATION_RECOVERABLE",
    }
    assert "synthetic-private-error-marker" not in output.out


def test_bridge_one_time_response_is_in_pipe_only(monkeypatch, capsys):
    module = bridge()

    async def issued(value):
        return {"status": "ok", "token": "synthetic-one-time-token-marker"}

    monkeypatch.setattr(module, "execute", issued)
    monkeypatch.setattr(module.sys, "stdin", StringIO("{}"))
    module.main()
    output = capsys.readouterr()
    assert not output.err
    assert json.loads(output.out)["token"] == "synthetic-one-time-token-marker"
