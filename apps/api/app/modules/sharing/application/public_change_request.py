from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID, uuid4

from aria_observability import StructuredEventLogger

from app.modules.sharing.application.change_request_ports import (
    ScopeChangeRequestRepositoryError,
    ScopeChangeRequestUnitOfWorkFactory,
)
from app.modules.sharing.application.ports import ScopeShareTokenHasher
from app.modules.sharing.application.public_decision_errors import (
    PublicScopeAlreadyApproved,
    PublicScopeChangesAlreadyRequested,
)
from app.modules.sharing.application.public_resolver import is_canonical_public_token
from app.modules.sharing.domain.scope_approval import normalize_guest_name
from app.modules.sharing.domain.scope_change_request import (
    NewScopeChangeRequest,
    ScopeChangeRequest,
    normalize_change_comment,
)


class PublicScopeChangeRequestNotFound(Exception):
    """The capability is malformed, unavailable, expired, revoked, or inaccessible."""


class PublicScopeChangeRequestIdempotencyConflict(Exception):
    """A guest idempotency key was reused with changed canonical semantics."""


@dataclass(frozen=True, slots=True)
class RequestPublicScopeChangesCommand:
    token: str
    guest_name: str
    comment: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class RequestPublicScopeChangesResult:
    change_request: ScopeChangeRequest
    replayed: bool


class PublicScopeChangeRequestService:
    def __init__(
        self,
        unit_of_work_factory: ScopeChangeRequestUnitOfWorkFactory,
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

    async def request_changes(
        self, command: RequestPublicScopeChangesCommand
    ) -> RequestPublicScopeChangesResult:
        started_at = perf_counter()
        guest_name = normalize_guest_name(command.guest_name)
        comment = normalize_change_comment(command.comment)
        if not command.idempotency_key.strip():
            raise ValueError("Idempotency-Key must not be empty")
        if not is_canonical_public_token(command.token):
            self._emit_not_found(started_at)
            raise PublicScopeChangeRequestNotFound

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
                    raise PublicScopeChangeRequestNotFound

                request_hash = _change_request_hash(
                    share_link_id=target.share_link_id,
                    token_hash=token_hash,
                    guest_name=guest_name,
                    comment=comment,
                )
                existing = await unit_of_work.repository.change_request_for_scope_version(
                    target.scope_version_id
                )
                if existing is not None:
                    if (
                        existing.share_link_id == target.share_link_id
                        and existing.idempotency_key == command.idempotency_key
                    ):
                        if existing.request_hash != request_hash:
                            raise PublicScopeChangeRequestIdempotencyConflict
                        self._event_logger.emit(
                            "scope_change_request.replayed",
                            scope_change_request_id=str(existing.id),
                            scope_share_link_id=str(existing.share_link_id),
                            scope_version_id=str(existing.scope_version_id),
                            version_no=existing.version_no,
                            operation="request_changes",
                            duration_ms=(perf_counter() - started_at) * 1000,
                            status="succeeded",
                        )
                        return RequestPublicScopeChangesResult(
                            change_request=existing,
                            replayed=True,
                        )
                    raise PublicScopeChangesAlreadyRequested

                if target.scope_status == "approved":
                    raise PublicScopeAlreadyApproved
                if target.scope_status == "changes_requested":
                    raise PublicScopeChangesAlreadyRequested
                if target.scope_status != "awaiting_approval":
                    self._emit_not_found(started_at)
                    raise PublicScopeChangeRequestNotFound

                change_request = await unit_of_work.repository.add(
                    NewScopeChangeRequest(
                        id=self._id_factory(),
                        account_id=target.account_id,
                        project_id=target.project_id,
                        scope_version_id=target.scope_version_id,
                        share_link_id=target.share_link_id,
                        version_no=target.version_no,
                        version_hash=target.version_hash,
                        guest_name=guest_name,
                        comment=comment,
                        idempotency_key=command.idempotency_key,
                        request_hash=request_hash,
                        requested_at=now,
                    )
                )
                await unit_of_work.repository.mark_scope_version_changes_requested(
                    target.scope_version_id
                )
                await unit_of_work.commit()
        except ScopeChangeRequestRepositoryError:
            self._event_logger.emit(
                "scope_change_request.persistence_failed",
                level="ERROR",
                operation="request_changes",
                duration_ms=(perf_counter() - started_at) * 1000,
                status="failed",
                error_code="SCOPE_CHANGE_REQUEST_PERSISTENCE_FAILURE",
            )
            raise

        self._event_logger.emit(
            "scope_change_request.created",
            scope_change_request_id=str(change_request.id),
            scope_share_link_id=str(change_request.share_link_id),
            scope_version_id=str(change_request.scope_version_id),
            version_no=change_request.version_no,
            operation="request_changes",
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return RequestPublicScopeChangesResult(change_request=change_request, replayed=False)

    def _emit_not_found(self, started_at: float) -> None:
        self._event_logger.emit(
            "scope_change_request.not_found",
            level="WARNING",
            operation="request_changes",
            reason_code="not_resolvable",
            duration_ms=(perf_counter() - started_at) * 1000,
            status="not_found",
            error_code="RESOURCE_NOT_FOUND",
        )


def _change_request_hash(
    *, share_link_id: UUID, token_hash: bytes, guest_name: str, comment: str
) -> str:
    canonical = json.dumps(
        {
            "comment": comment,
            "guest_name": guest_name,
            "share_link_id": str(share_link_id),
            "token_hash_reference": token_hash.hex(),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
