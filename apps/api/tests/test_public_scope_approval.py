from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.sharing.application.approval_ports import ScopeApprovalTarget
from app.modules.sharing.application.public_approval import (
    ApprovePublicScopeCommand,
    PublicScopeAlreadyApproved,
    PublicScopeApprovalIdempotencyConflict,
    PublicScopeApprovalNotFound,
    PublicScopeApprovalService,
)
from app.modules.sharing.domain.scope_approval import NewScopeApproval, ScopeApproval
from app.modules.sharing.infrastructure.tokens import SecureScopeShareTokenIssuer

NOW = datetime.now(UTC)


class FakeRepository:
    def __init__(self) -> None:
        self.target: ScopeApprovalTarget | None = ScopeApprovalTarget(
            account_id=uuid4(),
            project_id=uuid4(),
            share_link_id=uuid4(),
            scope_version_id=uuid4(),
            version_no=4,
            version_hash="sha256:" + "a" * 64,
            scope_status="awaiting_approval",
        )
        self.existing: ScopeApproval | None = None
        self.added: NewScopeApproval | None = None
        self.marked: list[object] = []
        self.resolve_calls: list[tuple[bytes, datetime]] = []

    async def resolve_target_for_update(self, *, token_hash: bytes, now: datetime):
        self.resolve_calls.append((token_hash, now))
        return self.target

    async def approval_for_scope_version(self, scope_version_id):
        assert self.target is not None
        assert scope_version_id == self.target.scope_version_id
        return self.existing

    async def add(self, approval: NewScopeApproval) -> ScopeApproval:
        self.added = approval
        return ScopeApproval(**asdict(approval))

    async def mark_scope_version_approved(self, scope_version_id):
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
    service = PublicScopeApprovalService(
        lambda: unit_of_work,
        issuer,
        logger,  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    return service, repository, unit_of_work, issuer, token, logger


def _command(token: str, **changes: object) -> ApprovePublicScopeCommand:
    values: dict[str, object] = {
        "token": token,
        "guest_name": "  A\u0301li جلیلی  ",
        "explicit_consent": True,
        "idempotency_key": "approve-1",
    }
    values.update(changes)
    return ApprovePublicScopeCommand(**values)  # type: ignore[arg-type]


def test_approval_normalizes_name_captures_hash_and_commits_one_transition() -> None:
    service, repository, unit_of_work, issuer, token, logger = _fixture()

    result = asyncio.run(service.approve(_command(token)))

    assert result.replayed is False
    assert result.approval.guest_name == "Áli جلیلی"
    assert result.approval.version_hash == "sha256:" + "a" * 64
    assert repository.resolve_calls == [(issuer.hash_public_token(token), NOW)]
    assert repository.marked == [result.approval.scope_version_id]
    assert unit_of_work.commits == 1
    assert logger.events[-1][0] == "scope_approval.created"
    serialized = repr(logger.events)
    assert token not in serialized
    assert "Áli جلیلی" not in serialized
    assert result.approval.version_hash not in serialized


def test_same_capability_key_and_canonical_request_replays_exact_business_result() -> None:
    service, repository, unit_of_work, _, token, logger = _fixture()
    created = asyncio.run(service.approve(_command(token)))
    repository.existing = created.approval
    assert repository.target is not None
    repository.target = replace(repository.target, scope_status="approved")

    replay = asyncio.run(service.approve(_command(token, guest_name="Áli جلیلی")))

    assert replay == type(replay)(approval=created.approval, replayed=True)
    assert unit_of_work.commits == 1
    assert logger.events[-1][0] == "scope_approval.replayed"


def test_changed_request_same_key_conflicts_and_different_key_is_already_approved() -> None:
    service, repository, _, _, token, _ = _fixture()
    created = asyncio.run(service.approve(_command(token)))
    repository.existing = created.approval

    with pytest.raises(PublicScopeApprovalIdempotencyConflict):
        asyncio.run(service.approve(_command(token, guest_name="نام متفاوت")))
    with pytest.raises(PublicScopeAlreadyApproved):
        asyncio.run(service.approve(_command(token, idempotency_key="approve-2")))


def test_capability_is_validated_before_state_and_non_approvable_state_fails_closed() -> None:
    service, repository, _, _, token, _ = _fixture()

    with pytest.raises(PublicScopeApprovalNotFound):
        asyncio.run(service.approve(_command("malformed")))
    assert repository.resolve_calls == []

    assert repository.target is not None
    repository.target = replace(repository.target, scope_status="superseded")
    with pytest.raises(PublicScopeApprovalNotFound):
        asyncio.run(service.approve(_command(token)))
