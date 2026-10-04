from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context

from app.modules.sharing.application.ports import ResolvedPublicScope
from app.modules.sharing.application.public_resolver import (
    PublicScopeShareNotFound,
    PublicScopeShareResolver,
)
from app.modules.sharing.infrastructure.tokens import SecureScopeShareTokenIssuer

NOW = datetime.now(UTC)


class FakeRepository:
    def __init__(self) -> None:
        self.result: ResolvedPublicScope | None = ResolvedPublicScope(
            share_link_id=uuid4(),
            scope_version_id=uuid4(),
            version_no=3,
            snapshot_data={"schema_version": "scope_content_schema_v1", "sections": []},
        )
        self.calls: list[tuple[bytes, datetime]] = []

    async def resolve_public(self, *, token_hash: bytes, now: datetime):
        self.calls.append((token_hash, now))
        return self.result


class FakeUnitOfWork:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


class RecordingHasher:
    def __init__(self) -> None:
        self.tokens: list[str] = []

    def hash_public_token(self, public_token: str) -> bytes:
        self.tokens.append(public_token)
        return SecureScopeShareTokenIssuer.hash_public_token(public_token)


@dataclass
class FakeLogger:
    events: list[tuple[str, dict[str, object]]]

    def emit(self, event_name: str, **fields: object) -> None:
        self.events.append((event_name, fields))


def _fixture():
    repository = FakeRepository()
    hasher = RecordingHasher()
    logger = FakeLogger([])
    resolver = PublicScopeShareResolver(
        lambda: FakeUnitOfWork(repository),
        hasher,
        logger,  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    return resolver, repository, hasher, logger


def _trace():
    return bind_trace_context(TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4())))


def test_valid_capability_is_hashed_once_and_returns_exact_snapshot() -> None:
    resolver, repository, hasher, logger = _fixture()
    issued = SecureScopeShareTokenIssuer().issue()

    with _trace():
        resolved = asyncio.run(resolver.resolve(token=issued.public_token))

    assert resolved is repository.result
    assert hasher.tokens == [issued.public_token]
    assert repository.calls == [(issued.token_hash, NOW)]
    assert logger.events[0][0] == "scope_share.resolve_succeeded"
    assert issued.public_token not in repr(logger.events)
    assert issued.token_hash.hex() not in repr(logger.events)


@pytest.mark.parametrize(
    "token",
    ["", "short", "=" * 43, "a" * 42, "الف" * 43, "a" * 44],
)
def test_malformed_capability_is_not_hashed_or_queried(token: str) -> None:
    resolver, repository, hasher, logger = _fixture()

    with _trace(), pytest.raises(PublicScopeShareNotFound):
        asyncio.run(resolver.resolve(token=token))

    assert hasher.tokens == []
    assert repository.calls == []
    assert logger.events[0][0] == "scope_share.resolve_not_found"
    if token:
        assert token not in repr(logger.events)


def test_unknown_expired_revoked_or_inaccessible_result_is_same_not_found() -> None:
    resolver, repository, _, logger = _fixture()
    repository.result = None
    issued = SecureScopeShareTokenIssuer().issue()

    with _trace(), pytest.raises(PublicScopeShareNotFound):
        asyncio.run(resolver.resolve(token=issued.public_token))

    assert logger.events[0][0] == "scope_share.resolve_not_found"
    assert logger.events[0][1]["reason_code"] == "not_resolvable"
    assert issued.public_token not in repr(logger.events)
