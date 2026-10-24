from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import UUID, uuid4

from aria_observability import StructuredEventLogger, enrich_trace_context

from app.modules.identity.application.tenant_context import TenantContext
from app.modules.scope.application.scope_revision_ports import (
    ScopeRevisionRepositoryError,
    ScopeRevisionUnitOfWorkFactory,
)
from app.modules.scope.domain.readiness import ScopeReadinessPolicy
from app.modules.scope.domain.scope_version import (
    SCOPE_SNAPSHOT_CANONICALIZATION_VERSION,
    NewScopeVersion,
    ScopeVersion,
    ScopeVersionValidationError,
    hash_scope_snapshot,
)


class ScopeRevisionAccessNotFound(Exception):
    """The tenant-scoped Project, target Version, or Change Request is not visible."""


class ScopeRevisionPermissionDenied(Exception):
    """The caller lacks an active Membership."""


class ScopeRevisionIdempotencyConflict(Exception):
    """An idempotency key was reused with different revision semantics."""


class ScopeRevisionStale(Exception):
    """The requested revision relationship has been invalidated."""


class ScopeRevisionVersionConflict(Exception):
    """The current Draft changed after the caller read it."""


class ScopeRevisionNotReady(Exception):
    """The current Scope has unresolved Critical Gaps."""


class ScopeRevisionUnchanged(Exception):
    """The current Draft is identical to the requested revision target."""


@dataclass(frozen=True, slots=True)
class CreateScopeRevisionCommand:
    change_request_id: UUID
    expected_draft_updated_at: datetime
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class ScopeRevisionResult:
    version: ScopeVersion
    replayed: bool


class ScopeRevisionService:
    def __init__(
        self,
        unit_of_work_factory: ScopeRevisionUnitOfWorkFactory,
        event_logger: StructuredEventLogger,
        *,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger
        self._id_factory = id_factory
        self._readiness_policy = ScopeReadinessPolicy()

    @staticmethod
    def request_hash(
        project_id: UUID,
        target_version_no: int,
        command: CreateScopeRevisionCommand,
    ) -> str:
        payload = json.dumps(
            {
                "change_request_id": str(command.change_request_id),
                "expected_draft_updated_at": command.expected_draft_updated_at.astimezone(
                    UTC
                ).isoformat(),
                "project_id": str(project_id),
                "target_version_no": target_version_no,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    async def create(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        target_version_no: int,
        command: CreateScopeRevisionCommand,
    ) -> ScopeRevisionResult:
        _require_active_context(context)
        if target_version_no < 1:
            raise ScopeVersionValidationError("target version number must be at least one")
        if command.expected_draft_updated_at.tzinfo is None:
            raise ScopeVersionValidationError("expected_draft_updated_at must include a timezone")
        if not command.idempotency_key.strip():
            raise ScopeVersionValidationError("Idempotency-Key must not be empty")
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        request_hash = self.request_hash(project_id, target_version_no, command)
        now = datetime.now(UTC)
        new_scope_version_id: UUID | None = None
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                visible = await unit_of_work.repository.lock_visible_target(
                    account_id=context.account_id,
                    project_id=project_id,
                    version_no=target_version_no,
                )
                if visible is None:
                    raise ScopeRevisionAccessNotFound

                reservation = await unit_of_work.repository.reserve_revision(
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    project_id=project_id,
                    target_version_no=target_version_no,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    scope_version_id=self._id_factory(),
                    now=now,
                    expires_at=now + timedelta(hours=24),
                )
                new_scope_version_id = reservation.scope_version_id
                if not reservation.acquired:
                    if reservation.request_hash != request_hash:
                        raise ScopeRevisionIdempotencyConflict
                    if reservation.response is None:
                        raise ScopeRevisionRepositoryError
                    return ScopeRevisionResult(version=reservation.response, replayed=True)

                target = await unit_of_work.repository.get_revision_target(
                    account_id=context.account_id,
                    project_id=project_id,
                    target_version_no=target_version_no,
                    change_request_id=command.change_request_id,
                )
                if target is None:
                    raise ScopeRevisionAccessNotFound
                if (
                    target.latest_scope_version_id != target.target.id
                    or target.target.status != "changes_requested"
                    or target.change_request_scope_version_id != target.target.id
                    or target.change_request_consumed
                    or target.draft is None
                    or target.draft.context_version != target.target.context_version
                    or target.project_current_context_version != target.target.context_version
                ):
                    raise ScopeRevisionStale

                draft = target.draft
                if draft.updated_at != command.expected_draft_updated_at:
                    self._event_logger.emit(
                        "scope_revision.version_conflict",
                        level="WARNING",
                        actor_id=str(context.subject_id),
                        scope_version_id=str(target.target.id),
                        status="conflict",
                        error_code="VERSION_CONFLICT",
                    )
                    raise ScopeRevisionVersionConflict

                readiness = self._readiness_policy.evaluate(
                    account_id=context.account_id,
                    project_id=project_id,
                    context_version=draft.context_version,
                    gaps=target.gaps,
                )
                if not readiness.ready_for_share:
                    raise ScopeRevisionNotReady

                snapshot_data = deepcopy(draft.content)
                snapshot_hash = hash_scope_snapshot(snapshot_data)
                if snapshot_hash == target.target.snapshot_hash:
                    raise ScopeRevisionUnchanged

                revision = NewScopeVersion(
                    id=reservation.scope_version_id,
                    account_id=context.account_id,
                    project_id=project_id,
                    version_no=target.target.version_no + 1,
                    context_version=draft.context_version,
                    status="awaiting_approval",
                    snapshot_data=snapshot_data,
                    snapshot_hash=snapshot_hash,
                    created_by=context.subject_id,
                    revision_of_scope_version_id=target.target.id,
                    change_request_id=command.change_request_id,
                )
                persisted = await unit_of_work.repository.add_revision(revision)
                await unit_of_work.repository.supersede_target(
                    target_scope_version_id=target.target.id
                )
                await unit_of_work.repository.complete_revision_reservation(
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    project_id=project_id,
                    target_version_no=target_version_no,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    version=persisted,
                )
                await unit_of_work.commit()
        except ScopeRevisionRepositoryError:
            fields: dict[str, object] = {
                "actor_id": str(context.subject_id),
                "component": "scope_revision_repository",
                "operation": "create_revision",
                "duration_ms": (perf_counter() - started_at) * 1000,
                "status": "failed",
                "error_code": "SCOPE_REVISION_FAILURE",
            }
            if new_scope_version_id is not None:
                fields["scope_version_id"] = str(new_scope_version_id)
            self._event_logger.emit("scope_revision.creation_failed", level="ERROR", **fields)
            raise

        self._event_logger.emit(
            "scope_revision.created",
            actor_id=str(context.subject_id),
            scope_version_id=str(persisted.id),
            revision_of_scope_version_id=str(target.target.id),
            version_no=persisted.version_no,
            context_version=persisted.context_version,
            schema_version=persisted.snapshot_data["schema_version"],
            canonicalization_version=SCOPE_SNAPSHOT_CANONICALIZATION_VERSION,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return ScopeRevisionResult(version=persisted, replayed=False)


def _require_active_context(context: TenantContext) -> None:
    if context.membership_status != "active":
        raise ScopeRevisionPermissionDenied
