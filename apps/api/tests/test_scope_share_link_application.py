from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context

from app.modules.identity.application.tenant_context import TenantContext
from app.modules.sharing.application.ports import (
    IssuedScopeShareToken,
    ScopeDecisionProjection,
    ScopeShareCreateTarget,
    ScopeShareLinkProjection,
)
from app.modules.sharing.application.service import (
    CreateScopeShareLinkCommand,
    RevokeScopeShareLinkCommand,
    ScopeShareLinkAccessNotFound,
    ScopeShareLinkIdempotencyConflict,
    ScopeShareLinkPermissionDenied,
    ScopeShareLinkService,
)
from app.modules.sharing.domain.scope_share_link import NewScopeShareLink, ScopeShareLink
from app.shared.idempotency import IdempotencyReservation

ACCOUNT_ID, PROJECT_ID, VERSION_ID, SUBJECT = uuid4(), uuid4(), uuid4(), uuid4()
NOW = datetime.now(UTC)


def _context(*, role="member", status="active", subject_id=SUBJECT) -> TenantContext:
    return TenantContext(
        subject_id=subject_id,
        account_id=ACCOUNT_ID,
        membership_id=uuid4(),
        role=role,
        membership_status=status,
    )


class FakeTokenIssuer:
    def __init__(self) -> None:
        self.calls = 0

    def issue(self) -> IssuedScopeShareToken:
        self.calls += 1
        return IssuedScopeShareToken(public_token="public-once", token_hash=b"h" * 32)


class FakeIdempotency:
    def __init__(self) -> None:
        self.records: dict[tuple[UUID, UUID, str, str], dict[str, object]] = {}

    async def reserve(self, **values: object) -> IdempotencyReservation:
        key = (
            values["account_id"],
            values["actor_id"],
            values["route_key"],
            values["idempotency_key"],
        )
        existing = self.records.get(key)
        if existing is not None:
            return IdempotencyReservation(
                acquired=False,
                request_hash=str(existing["request_hash"]),
                response_status=existing.get("response_status"),
                response_ref=existing.get("response_ref"),
            )
        self.records[key] = {"request_hash": values["request_hash"]}
        return IdempotencyReservation(
            acquired=True,
            request_hash=str(values["request_hash"]),
            response_status=None,
            response_ref=None,
        )

    async def complete(self, **values: object) -> None:
        key = (
            values["account_id"],
            values["actor_id"],
            values["route_key"],
            values["idempotency_key"],
        )
        self.records[key].update(
            response_status=values["response_status"],
            response_ref=values["response_ref"],
        )


class FakeRepository:
    def __init__(self) -> None:
        self.target_id: UUID | None = VERSION_ID
        self.target_status = "awaiting_approval"
        self.links: dict[UUID, ScopeShareLink] = {}
        self.revocation_writes = 0
        self.list_actor_id: UUID | None = None
        self.decision = ScopeDecisionProjection(
            decision_type="none",
            scope_version_no=1,
        )

    @staticmethod
    def create_route_key(project_id: UUID) -> str:
        return f"POST:/api/v1/projects/{project_id}/scope/versions/share"

    @staticmethod
    def revoke_route_key(project_id: UUID) -> str:
        return f"POST:/api/v1/projects/{project_id}/scope-shares/revoke"

    async def scope_version_id(self, **_: object) -> UUID | None:
        return self.target_id

    async def lock_scope_version_for_share_create(
        self, **_: object
    ) -> ScopeShareCreateTarget | None:
        if self.target_id is None:
            return None
        return ScopeShareCreateTarget(id=self.target_id, status=self.target_status)  # type: ignore[arg-type]

    async def scope_version_exists(self, **_: object) -> bool:
        return self.target_id is not None

    async def add(self, link: NewScopeShareLink) -> ScopeShareLink:
        persisted = ScopeShareLink(
            id=link.id,
            account_id=link.account_id,
            project_id=link.project_id,
            scope_version_id=link.scope_version_id,
            token_hash=link.token_hash,
            expires_at=link.expires_at,
            revoked_at=None,
            created_by=link.created_by,
            created_at=link.created_at,
        )
        self.links[persisted.id] = persisted
        return persisted

    async def get_for_update(self, *, share_link_id: UUID, **_: object) -> ScopeShareLink | None:
        return self.links.get(share_link_id)

    async def set_revoked(self, link: ScopeShareLink) -> ScopeShareLink:
        self.revocation_writes += 1
        self.links[link.id] = link
        return link

    async def list_for_scope_version(
        self, *, actor_id: UUID | None, **_: object
    ) -> tuple[ScopeShareLinkProjection, ...]:
        self.list_actor_id = actor_id
        return tuple(
            ScopeShareLinkProjection(link=link, scope_version_no=1)
            for link in self.links.values()
            if actor_id is None or link.created_by == actor_id
        )

    async def decision_for_scope_version(self, **_: object) -> ScopeDecisionProjection:
        return self.decision


class FakeUnitOfWork:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository
        self.idempotency = FakeIdempotency()
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


def _service(repository: FakeRepository, logger: FakeLogger | None = None):
    unit_of_work = FakeUnitOfWork(repository)
    issuer = FakeTokenIssuer()
    ids = iter(UUID(int=value) for value in range(135, 150))
    service = ScopeShareLinkService(
        lambda: unit_of_work,
        issuer,
        logger or FakeLogger([]),  # type: ignore[arg-type]
        id_factory=lambda: next(ids),
        clock=lambda: NOW,
    )
    return service, unit_of_work, issuer


def _create_command(*, key="create-key", days=1) -> CreateScopeShareLinkCommand:
    return CreateScopeShareLinkCommand(
        version_no=1,
        expires_at=NOW + timedelta(days=days),
        idempotency_key=key,
    )


def _trace():
    return bind_trace_context(TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4())))


def test_active_member_creates_and_replays_without_issuing_a_second_token() -> None:
    repository = FakeRepository()
    logger = FakeLogger([])
    service, unit_of_work, issuer = _service(repository, logger)

    with _trace():
        first = asyncio.run(
            service.create(_context(), project_id=PROJECT_ID, command=_create_command())
        )
        replay = asyncio.run(
            service.create(_context(), project_id=PROJECT_ID, command=_create_command())
        )

    assert first.public_token == "public-once"
    assert first.token_available is True
    assert first.replayed is False
    assert replay.link.id == first.link.id
    assert replay.public_token is None
    assert replay.token_available is False
    assert replay.replayed is True
    assert issuer.calls == 1
    assert len(repository.links) == 1
    assert unit_of_work.commits == 1
    assert logger.events[0][0] == "scope_share_link.created"
    assert "public_token" not in logger.events[0][1]
    assert "token_hash" not in logger.events[0][1]
    response_ref = next(iter(unit_of_work.idempotency.records.values()))["response_ref"]
    assert response_ref == {"scope_share_link_id": str(first.link.id)}


def test_changed_create_payload_conflicts_without_new_token_or_link() -> None:
    repository = FakeRepository()
    service, _, issuer = _service(repository)
    with _trace():
        asyncio.run(service.create(_context(), project_id=PROJECT_ID, command=_create_command()))
        with pytest.raises(ScopeShareLinkIdempotencyConflict):
            asyncio.run(
                service.create(
                    _context(),
                    project_id=PROJECT_ID,
                    command=_create_command(days=2),
                )
            )
    assert issuer.calls == 1
    assert len(repository.links) == 1


def test_missing_or_cross_tenant_version_is_safe_not_found_before_reservation() -> None:
    repository = FakeRepository()
    repository.target_id = None
    service, unit_of_work, issuer = _service(repository)

    with _trace(), pytest.raises(ScopeShareLinkAccessNotFound):
        asyncio.run(service.create(_context(), project_id=PROJECT_ID, command=_create_command()))
    assert unit_of_work.commits == 0
    assert unit_of_work.idempotency.records == {}
    assert issuer.calls == 0


def test_superseded_version_cannot_create_a_new_share_capability() -> None:
    repository = FakeRepository()
    repository.target_status = "superseded"
    service, unit_of_work, issuer = _service(repository)

    with _trace(), pytest.raises(ScopeShareLinkAccessNotFound):
        asyncio.run(service.create(_context(), project_id=PROJECT_ID, command=_create_command()))

    assert unit_of_work.commits == 0
    assert unit_of_work.idempotency.records == {}
    assert issuer.calls == 0
    assert repository.links == {}


def test_revoke_is_idempotent_and_changed_target_conflicts() -> None:
    repository = FakeRepository()
    service, unit_of_work, _ = _service(repository)
    with _trace():
        created = asyncio.run(
            service.create(_context(), project_id=PROJECT_ID, command=_create_command())
        )
        command = RevokeScopeShareLinkCommand(idempotency_key="revoke-key")
        first = asyncio.run(
            service.revoke(
                _context(),
                project_id=PROJECT_ID,
                share_link_id=created.link.id,
                command=command,
            )
        )
        replay = asyncio.run(
            service.revoke(
                _context(),
                project_id=PROJECT_ID,
                share_link_id=created.link.id,
                command=command,
            )
        )
        other = ScopeShareLink(
            id=uuid4(),
            account_id=ACCOUNT_ID,
            project_id=PROJECT_ID,
            scope_version_id=VERSION_ID,
            token_hash=b"x" * 32,
            expires_at=NOW + timedelta(days=1),
            revoked_at=None,
            created_by=SUBJECT,
            created_at=NOW,
        )
        repository.links[other.id] = other
        with pytest.raises(ScopeShareLinkIdempotencyConflict):
            asyncio.run(
                service.revoke(
                    _context(),
                    project_id=PROJECT_ID,
                    share_link_id=other.id,
                    command=command,
                )
            )

    assert first.revoked_at == NOW
    assert replay == first
    assert repository.revocation_writes == 1
    assert unit_of_work.commits == 2


def test_member_cannot_revoke_another_creators_link_but_admin_can() -> None:
    repository = FakeRepository()
    service, _, _ = _service(repository)
    creator = uuid4()
    with _trace():
        created = asyncio.run(
            service.create(
                _context(subject_id=creator),
                project_id=PROJECT_ID,
                command=_create_command(),
            )
        )
        with pytest.raises(ScopeShareLinkAccessNotFound):
            asyncio.run(
                service.revoke(
                    _context(),
                    project_id=PROJECT_ID,
                    share_link_id=created.link.id,
                    command=RevokeScopeShareLinkCommand(idempotency_key="member-denied"),
                )
            )
        revoked = asyncio.run(
            service.revoke(
                _context(role="admin"),
                project_id=PROJECT_ID,
                share_link_id=created.link.id,
                command=RevokeScopeShareLinkCommand(idempotency_key="admin-revoke"),
            )
        )
    assert revoked.revoked_at == NOW


def test_inactive_membership_is_denied_before_repository_access() -> None:
    repository = FakeRepository()
    service, unit_of_work, issuer = _service(repository)
    with _trace(), pytest.raises(ScopeShareLinkPermissionDenied):
        asyncio.run(
            service.create(
                _context(status="suspended"),
                project_id=PROJECT_ID,
                command=_create_command(),
            )
        )
    assert unit_of_work.idempotency.records == {}
    assert issuer.calls == 0


def test_share_projection_filters_members_and_computes_status_and_revoke_capability() -> None:
    repository = FakeRepository()
    service, _, _ = _service(repository)
    member_link = ScopeShareLink(
        id=uuid4(),
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        scope_version_id=VERSION_ID,
        token_hash=b"m" * 32,
        expires_at=NOW + timedelta(hours=1),
        revoked_at=None,
        created_by=SUBJECT,
        created_at=NOW,
    )
    other_link = ScopeShareLink(
        id=uuid4(),
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        scope_version_id=VERSION_ID,
        token_hash=b"o" * 32,
        expires_at=NOW - timedelta(hours=1),
        revoked_at=None,
        created_by=uuid4(),
        created_at=NOW - timedelta(days=1),
    )
    repository.links = {member_link.id: member_link, other_link.id: other_link}

    member_rows = asyncio.run(
        service.list_for_version(_context(), project_id=PROJECT_ID, version_no=1)
    )
    assert [row.id for row in member_rows] == [member_link.id]
    assert member_rows[0].status == "active"
    assert member_rows[0].can_revoke is True
    assert repository.list_actor_id == SUBJECT

    admin_rows = asyncio.run(
        service.list_for_version(_context(role="admin"), project_id=PROJECT_ID, version_no=1)
    )
    assert {row.id for row in admin_rows} == {member_link.id, other_link.id}
    assert {row.status for row in admin_rows} == {"active", "expired"}
    assert repository.list_actor_id is None


def test_decision_projection_is_exact_version_and_content_is_not_logged() -> None:
    repository = FakeRepository()
    comment = "این متن فقط در پاسخ مجاز برمی‌گردد"
    repository.decision = ScopeDecisionProjection(
        decision_type="change_request",
        scope_version_no=1,
        decision_id=uuid4(),
        guest_name="مهمان مصنوعی",
        comment=comment,
        decided_at=NOW,
    )
    logger = FakeLogger([])
    service, _, _ = _service(repository, logger)

    decision = asyncio.run(
        service.decision_for_version(_context(), project_id=PROJECT_ID, version_no=1)
    )

    assert decision is repository.decision
    assert comment not in repr(logger.events)
