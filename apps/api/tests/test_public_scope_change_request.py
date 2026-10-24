from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.sharing.application.change_request_ports import ScopeChangeRequestTarget
from app.modules.sharing.application.public_change_request import (
    PublicScopeChangeRequestIdempotencyConflict,
    PublicScopeChangeRequestNotFound,
    PublicScopeChangeRequestService,
    RequestPublicScopeChangesCommand,
)
from app.modules.sharing.application.public_decision_errors import (
    PublicScopeAlreadyApproved,
    PublicScopeChangesAlreadyRequested,
)
from app.modules.sharing.domain.scope_change_request import (
    NewScopeChangeRequest,
    ScopeChangeRequest,
)
from app.modules.sharing.infrastructure.tokens import SecureScopeShareTokenIssuer

NOW = datetime.now(UTC)


class FakeRepository:
    def __init__(self) -> None:
        self.target: ScopeChangeRequestTarget | None = ScopeChangeRequestTarget(
            account_id=uuid4(),
            project_id=uuid4(),
            share_link_id=uuid4(),
            scope_version_id=uuid4(),
            version_no=4,
            version_hash="sha256:" + "a" * 64,
            scope_status="awaiting_approval",
        )
        self.existing: ScopeChangeRequest | None = None
        self.marked: list[object] = []
        self.resolve_calls: list[tuple[bytes, datetime]] = []

    async def resolve_target_for_update(self, *, token_hash: bytes, now: datetime):
        self.resolve_calls.append((token_hash, now))
        return self.target

    async def change_request_for_scope_version(self, scope_version_id):
        assert self.target is not None
        assert scope_version_id == self.target.scope_version_id
        return self.existing

    async def add(self, change_request: NewScopeChangeRequest) -> ScopeChangeRequest:
        return ScopeChangeRequest(**asdict(change_request))

    async def mark_scope_version_changes_requested(self, scope_version_id):
        self.marked.append(scope_version_id)


class FakeUnitOfWork:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


@dataclass
class FakeLogger:
    events: list[tuple[str, dict[str, object]]]

    def emit(self, event_name: str, **fields: object) -> None:
        self.events.append((event_name, fields))


def _fixture():
    repository = FakeRepository()
    unit_of_work = FakeUnitOfWork(repository)
    issuer = SecureScopeShareTokenIssuer()
    token = issuer.issue().public_token
    logger = FakeLogger([])
    service = PublicScopeChangeRequestService(
        lambda: unit_of_work,
        issuer,
        logger,  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    return service, repository, unit_of_work, issuer, token, logger


def _command(token: str, **changes: object) -> RequestPublicScopeChangesCommand:
    values: dict[str, object] = {
        "token": token,
        "guest_name": "  A\u0301li جلیلی  ",
        "comment": "  خط اول\r\n  خط دوم  ",
        "idempotency_key": "change-1",
    }
    values.update(changes)
    return RequestPublicScopeChangesCommand(**values)  # type: ignore[arg-type]


def test_request_normalizes_input_captures_snapshot_and_commits_once() -> None:
    service, repository, unit_of_work, issuer, token, logger = _fixture()

    result = asyncio.run(service.request_changes(_command(token)))

    assert result.replayed is False
    assert result.change_request.guest_name == "Áli جلیلی"
    assert result.change_request.comment == "خط اول\n  خط دوم"
    assert result.change_request.version_hash == "sha256:" + "a" * 64
    assert repository.resolve_calls == [(issuer.hash_public_token(token), NOW)]
    assert repository.marked == [result.change_request.scope_version_id]
    assert unit_of_work.commits == 1
    assert logger.events[-1][0] == "scope_change_request.created"
    serialized = repr(logger.events)
    for forbidden in (token, "Áli جلیلی", "خط اول", result.change_request.version_hash):
        assert forbidden not in serialized


def test_replay_returns_same_result_and_changed_semantics_conflict() -> None:
    service, repository, unit_of_work, _, token, _ = _fixture()
    created = asyncio.run(service.request_changes(_command(token)))
    repository.existing = created.change_request
    assert repository.target is not None
    repository.target = replace(repository.target, scope_status="changes_requested")

    replay = asyncio.run(
        service.request_changes(
            _command(token, guest_name="Áli جلیلی", comment="خط اول\n  خط دوم")
        )
    )
    assert replay.change_request == created.change_request
    assert replay.replayed is True
    assert unit_of_work.commits == 1

    with pytest.raises(PublicScopeChangeRequestIdempotencyConflict):
        asyncio.run(service.request_changes(_command(token, comment="متن متفاوت")))
    with pytest.raises(PublicScopeChangesAlreadyRequested):
        asyncio.run(service.request_changes(_command(token, idempotency_key="change-2")))


def test_invalid_capability_and_non_decidable_states_fail_closed() -> None:
    service, repository, _, _, token, _ = _fixture()

    with pytest.raises(PublicScopeChangeRequestNotFound):
        asyncio.run(service.request_changes(_command("malformed")))
    assert repository.resolve_calls == []

    assert repository.target is not None
    repository.target = replace(repository.target, scope_status="superseded")
    with pytest.raises(PublicScopeChangeRequestNotFound):
        asyncio.run(service.request_changes(_command(token)))

    repository.target = replace(repository.target, scope_status="approved")
    with pytest.raises(PublicScopeAlreadyApproved):
        asyncio.run(service.request_changes(_command(token)))
