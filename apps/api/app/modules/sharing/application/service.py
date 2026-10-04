from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import UUID, uuid4

from aria_observability import StructuredEventLogger, enrich_trace_context

from app.modules.identity.application.tenant_context import TenantContext
from app.modules.sharing.application.ports import (
    ScopeShareLinkRepositoryError,
    ScopeShareLinkUnitOfWork,
    ScopeShareLinkUnitOfWorkFactory,
    ScopeShareTokenIssuer,
)
from app.modules.sharing.domain.scope_share_link import (
    NewScopeShareLink,
    ScopeShareLink,
    ScopeShareLinkValidationError,
)

SCOPE_SHARE_IDEMPOTENCY_TTL = timedelta(hours=24)


class ScopeShareLinkAccessNotFound(Exception):
    """The tenant-scoped Scope Version or Share Link is not visible."""


class ScopeShareLinkPermissionDenied(Exception):
    """The caller lacks an active Membership."""


class ScopeShareLinkIdempotencyConflict(Exception):
    """An idempotency key was reused for a different Share command."""


@dataclass(frozen=True, slots=True)
class CreateScopeShareLinkCommand:
    version_no: int
    expires_at: datetime
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class RevokeScopeShareLinkCommand:
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class CreateScopeShareLinkResult:
    link: ScopeShareLink
    public_token: str | None
    token_available: bool
    replayed: bool


class ScopeShareLinkService:
    def __init__(
        self,
        unit_of_work_factory: ScopeShareLinkUnitOfWorkFactory,
        token_issuer: ScopeShareTokenIssuer,
        event_logger: StructuredEventLogger,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._token_issuer = token_issuer
        self._event_logger = event_logger
        self._id_factory = id_factory
        self._clock = clock

    async def create(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        command: CreateScopeShareLinkCommand,
    ) -> CreateScopeShareLinkResult:
        _require_active_context(context)
        now = self._clock()
        _validate_create_command(command, now=now)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        share_link_id = self._id_factory()
        request_hash = _create_request_hash(
            context=context,
            project_id=project_id,
            version_no=command.version_no,
            expires_at=command.expires_at,
        )
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                scope_version_id = await unit_of_work.repository.scope_version_id(
                    account_id=context.account_id,
                    project_id=project_id,
                    version_no=command.version_no,
                )
                if scope_version_id is None:
                    raise ScopeShareLinkAccessNotFound

                route_key = unit_of_work.repository.create_route_key(project_id)
                reservation = await unit_of_work.idempotency.reserve(
                    record_id=self._id_factory(),
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=route_key,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    now=now,
                    expires_at=now + SCOPE_SHARE_IDEMPOTENCY_TTL,
                )
                if not reservation.acquired:
                    if reservation.request_hash != request_hash:
                        raise ScopeShareLinkIdempotencyConflict
                    link = await _load_replayed_link(
                        unit_of_work=unit_of_work,
                        response_ref=reservation.response_ref,
                        context=context,
                        project_id=project_id,
                    )
                    return CreateScopeShareLinkResult(
                        link=link,
                        public_token=None,
                        token_available=False,
                        replayed=True,
                    )

                issued = self._token_issuer.issue()
                link = await unit_of_work.repository.add(
                    NewScopeShareLink(
                        id=share_link_id,
                        account_id=context.account_id,
                        project_id=project_id,
                        scope_version_id=scope_version_id,
                        token_hash=issued.token_hash,
                        expires_at=command.expires_at,
                        created_by=context.subject_id,
                        created_at=now,
                    )
                )
                await unit_of_work.idempotency.complete(
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=route_key,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    response_status=201,
                    response_ref={"scope_share_link_id": str(link.id)},
                )
                await unit_of_work.commit()
        except ScopeShareLinkRepositoryError:
            self._emit_persistence_failure(
                context=context,
                project_id=project_id,
                share_link_id=share_link_id,
                operation="create",
                started_at=started_at,
            )
            raise

        self._event_logger.emit(
            "scope_share_link.created",
            actor_id=str(context.subject_id),
            scope_share_link_id=str(link.id),
            scope_version_id=str(link.scope_version_id),
            operation="create",
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return CreateScopeShareLinkResult(
            link=link,
            public_token=issued.public_token,
            token_available=True,
            replayed=False,
        )

    async def revoke(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        share_link_id: UUID,
        command: RevokeScopeShareLinkCommand,
    ) -> ScopeShareLink:
        _require_active_context(context)
        if not command.idempotency_key.strip():
            raise ScopeShareLinkValidationError("Idempotency-Key must not be empty")
        now = self._clock()
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                link = await unit_of_work.repository.get_for_update(
                    account_id=context.account_id,
                    project_id=project_id,
                    share_link_id=share_link_id,
                )
                if link is None:
                    raise ScopeShareLinkAccessNotFound
                if context.role not in {"owner", "admin"} and link.created_by != context.subject_id:
                    raise ScopeShareLinkAccessNotFound

                request_hash = _revoke_request_hash(
                    context=context,
                    project_id=project_id,
                    share_link_id=share_link_id,
                )
                route_key = unit_of_work.repository.revoke_route_key(project_id)
                reservation = await unit_of_work.idempotency.reserve(
                    record_id=self._id_factory(),
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=route_key,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    now=now,
                    expires_at=now + SCOPE_SHARE_IDEMPOTENCY_TTL,
                )
                if not reservation.acquired:
                    if reservation.request_hash != request_hash:
                        raise ScopeShareLinkIdempotencyConflict
                    _validate_revoke_replay(
                        response_ref=reservation.response_ref,
                        expected_share_link_id=share_link_id,
                    )
                    return link

                if link.revoked_at is None:
                    event_name = "scope_share_link.revoked"
                    result = await unit_of_work.repository.set_revoked(link.revoke(now=now))
                else:
                    event_name = "scope_share_link.revoke_replayed"
                    result = link
                await unit_of_work.idempotency.complete(
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=route_key,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    response_status=204,
                    response_ref={"scope_share_link_id": str(link.id)},
                )
                await unit_of_work.commit()
        except ScopeShareLinkRepositoryError:
            self._emit_persistence_failure(
                context=context,
                project_id=project_id,
                share_link_id=share_link_id,
                operation="revoke",
                started_at=started_at,
            )
            raise

        self._event_logger.emit(
            event_name,
            actor_id=str(context.subject_id),
            scope_share_link_id=str(result.id),
            scope_version_id=str(result.scope_version_id),
            operation="revoke",
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return result

    def _emit_persistence_failure(
        self,
        *,
        context: TenantContext,
        project_id: UUID,
        share_link_id: UUID,
        operation: str,
        started_at: float,
    ) -> None:
        self._event_logger.emit(
            "scope_share_link.persistence_failed",
            level="ERROR",
            actor_id=str(context.subject_id),
            project_id=str(project_id),
            scope_share_link_id=str(share_link_id),
            operation=operation,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="failed",
            error_code="SCOPE_SHARE_LINK_PERSISTENCE_FAILURE",
        )


def _validate_create_command(command: CreateScopeShareLinkCommand, *, now: datetime) -> None:
    if command.version_no < 1:
        raise ScopeShareLinkValidationError("version_no must be at least one")
    if not command.idempotency_key.strip():
        raise ScopeShareLinkValidationError("Idempotency-Key must not be empty")
    if command.expires_at.tzinfo is None or command.expires_at <= now:
        raise ScopeShareLinkValidationError(
            "expires_at must be timezone-aware and later than creation time"
        )


def _create_request_hash(
    *, context: TenantContext, project_id: UUID, version_no: int, expires_at: datetime
) -> str:
    return _hash_request(
        {
            "account_id": str(context.account_id),
            "actor_id": str(context.subject_id),
            "expires_at": expires_at.astimezone(UTC).isoformat(),
            "project_id": str(project_id),
            "version_no": version_no,
        }
    )


def _revoke_request_hash(
    *, context: TenantContext, project_id: UUID, share_link_id: UUID
) -> str:
    return _hash_request(
        {
            "account_id": str(context.account_id),
            "actor_id": str(context.subject_id),
            "project_id": str(project_id),
            "share_link_id": str(share_link_id),
        }
    )


def _hash_request(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_revoke_replay(
    *, response_ref: dict[str, object] | None, expected_share_link_id: UUID
) -> None:
    if response_ref is None:
        raise ScopeShareLinkRepositoryError
    try:
        persisted_share_link_id = UUID(str(response_ref["scope_share_link_id"]))
    except (KeyError, TypeError, ValueError):
        raise ScopeShareLinkRepositoryError from None
    if persisted_share_link_id != expected_share_link_id:
        raise ScopeShareLinkRepositoryError


async def _load_replayed_link(
    *,
    unit_of_work: ScopeShareLinkUnitOfWork,
    response_ref: dict[str, object] | None,
    context: TenantContext,
    project_id: UUID,
) -> ScopeShareLink:
    if response_ref is None:
        raise ScopeShareLinkRepositoryError
    try:
        share_link_id = UUID(str(response_ref["scope_share_link_id"]))
    except (KeyError, TypeError, ValueError):
        raise ScopeShareLinkRepositoryError from None
    link = await unit_of_work.repository.get_for_update(
        account_id=context.account_id,
        project_id=project_id,
        share_link_id=share_link_id,
    )
    if link is None:
        raise ScopeShareLinkRepositoryError
    return link


def _require_active_context(context: TenantContext) -> None:
    if context.membership_status != "active" or context.role not in {
        "owner",
        "admin",
        "member",
    }:
        raise ScopeShareLinkPermissionDenied
