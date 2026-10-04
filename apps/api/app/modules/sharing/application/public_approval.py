from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID, uuid4

from aria_observability import StructuredEventLogger

from app.modules.sharing.application.approval_ports import (
    ScopeApprovalRepositoryError,
    ScopeApprovalUnitOfWorkFactory,
)
from app.modules.sharing.application.ports import ScopeShareTokenHasher
from app.modules.sharing.application.public_resolver import is_canonical_public_token
from app.modules.sharing.domain.scope_approval import (
    NewScopeApproval,
    ScopeApproval,
    normalize_guest_name,
)


class PublicScopeApprovalNotFound(Exception):
    """The capability is malformed, unavailable, expired, revoked, or inaccessible."""


class PublicScopeAlreadyApproved(Exception):
    """The exact Scope Version already has its one final Approval."""


class PublicScopeApprovalIdempotencyConflict(Exception):
    """A guest idempotency key was reused with changed canonical semantics."""


@dataclass(frozen=True, slots=True)
class ApprovePublicScopeCommand:
    token: str
    guest_name: str
    explicit_consent: bool
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class ApprovePublicScopeResult:
    approval: ScopeApproval
    replayed: bool


class PublicScopeApprovalService:
    def __init__(
        self,
        unit_of_work_factory: ScopeApprovalUnitOfWorkFactory,
        token_hasher: ScopeShareTokenHasher,
        event_logger: StructuredEventLogger,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._token_hasher = token_hasher
        self._event_logger = event_logger
        self._id_factory = id_factory
        self._clock = clock

    async def approve(self, command: ApprovePublicScopeCommand) -> ApprovePublicScopeResult:
        started_at = perf_counter()
        guest_name = normalize_guest_name(command.guest_name)
        if command.explicit_consent is not True:
            raise ValueError("explicit_consent must be true")
        if not command.idempotency_key.strip():
            raise ValueError("Idempotency-Key must not be empty")
        if not is_canonical_public_token(command.token):
            self._emit_not_found(started_at)
            raise PublicScopeApprovalNotFound

        token_hash = self._token_hasher.hash_public_token(command.token)
        now = self._clock()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                target = await unit_of_work.repository.resolve_target_for_update(
                    token_hash=token_hash,
                    now=now,
                )
                if target is None:
                    self._emit_not_found(started_at)
                    raise PublicScopeApprovalNotFound

                request_hash = _approval_request_hash(
                    share_link_id=target.share_link_id,
                    token_hash=token_hash,
                    guest_name=guest_name,
                    explicit_consent=True,
                )
                existing = await unit_of_work.repository.approval_for_scope_version(
                    target.scope_version_id
                )
                if existing is not None:
                    if (
                        existing.share_link_id == target.share_link_id
                        and existing.idempotency_key == command.idempotency_key
                    ):
                        if existing.request_hash != request_hash:
                            raise PublicScopeApprovalIdempotencyConflict
                        self._event_logger.emit(
                            "scope_approval.replayed",
                            scope_approval_id=str(existing.id),
                            scope_share_link_id=str(existing.share_link_id),
                            scope_version_id=str(existing.scope_version_id),
                            version_no=existing.version_no,
                            operation="approve",
                            duration_ms=(perf_counter() - started_at) * 1000,
                            status="succeeded",
                        )
                        return ApprovePublicScopeResult(approval=existing, replayed=True)
                    raise PublicScopeAlreadyApproved

                if target.scope_status == "approved":
                    raise PublicScopeAlreadyApproved
                if target.scope_status != "awaiting_approval":
                    self._emit_not_found(started_at)
                    raise PublicScopeApprovalNotFound

                approval = await unit_of_work.repository.add(
                    NewScopeApproval(
                        id=self._id_factory(),
                        account_id=target.account_id,
                        project_id=target.project_id,
                        scope_version_id=target.scope_version_id,
                        share_link_id=target.share_link_id,
                        version_no=target.version_no,
                        version_hash=target.version_hash,
                        guest_name=guest_name,
                        explicit_consent=True,
                        idempotency_key=command.idempotency_key,
                        request_hash=request_hash,
                        approved_at=now,
                    )
                )
                await unit_of_work.repository.mark_scope_version_approved(target.scope_version_id)
                await unit_of_work.commit()
        except ScopeApprovalRepositoryError:
            self._event_logger.emit(
                "scope_approval.persistence_failed",
                level="ERROR",
                operation="approve",
                duration_ms=(perf_counter() - started_at) * 1000,
                status="failed",
                error_code="SCOPE_APPROVAL_PERSISTENCE_FAILURE",
            )
            raise

        self._event_logger.emit(
            "scope_approval.created",
            scope_approval_id=str(approval.id),
            scope_share_link_id=str(approval.share_link_id),
            scope_version_id=str(approval.scope_version_id),
            version_no=approval.version_no,
            operation="approve",
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return ApprovePublicScopeResult(approval=approval, replayed=False)

    def _emit_not_found(self, started_at: float) -> None:
        self._event_logger.emit(
            "scope_approval.not_found",
            level="WARNING",
            operation="approve",
            reason_code="not_resolvable",
            duration_ms=(perf_counter() - started_at) * 1000,
            status="not_found",
            error_code="RESOURCE_NOT_FOUND",
        )


def _approval_request_hash(
    *, share_link_id: UUID, token_hash: bytes, guest_name: str, explicit_consent: bool
) -> str:
    canonical = json.dumps(
        {
            "explicit_consent": explicit_consent,
            "guest_name": guest_name,
            "share_link_id": str(share_link_id),
            "token_hash_reference": token_hash.hex(),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
