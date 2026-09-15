from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import UUID, uuid4

from aria_observability import StructuredEventLogger, emit_product_analytics, enrich_trace_context

from app.modules.identity.application.tenant_context import TenantContext
from app.modules.scope.application.version_ports import (
    ScopeVersionRepositoryError,
    ScopeVersionUnitOfWorkFactory,
)
from app.modules.scope.domain.readiness import ScopeReadinessPolicy
from app.modules.scope.domain.scope_version import (
    SCOPE_SNAPSHOT_CANONICALIZATION_VERSION,
    NewScopeVersion,
    ScopeVersion,
    ScopeVersionValidationError,
    hash_scope_snapshot,
)


class ScopeVersionAccessNotFound(Exception):
    """The tenant-scoped Project, Draft, or Scope Version does not exist."""


class ScopeVersionPermissionDenied(Exception):
    """The caller lacks an active Membership."""


class ScopeVersionCreateConflict(Exception):
    """The current Draft changed after the caller read it."""


class ScopeVersionNotReady(Exception):
    """The current Scope has unresolved Critical Gaps."""


class ScopeVersionUnchanged(Exception):
    """The current Scope snapshot is identical to the latest version."""


class ScopeVersionIdempotencyConflict(Exception):
    """An idempotency key was reused for a different freeze request."""


@dataclass(frozen=True, slots=True)
class CreateScopeVersionCommand:
    expected_draft_updated_at: datetime
    idempotency_key: str


class ScopeVersionService:
    def __init__(
        self,
        unit_of_work_factory: ScopeVersionUnitOfWorkFactory,
        event_logger: StructuredEventLogger,
        *,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger
        self._id_factory = id_factory
        self._readiness_policy = ScopeReadinessPolicy()

    @staticmethod
    def request_hash(project_id: UUID, expected_draft_updated_at: datetime) -> str:
        payload = json.dumps(
            {
                "expected_draft_updated_at": expected_draft_updated_at.astimezone(UTC).isoformat(),
                "project_id": str(project_id),
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
        command: CreateScopeVersionCommand,
    ) -> ScopeVersion:
        _require_active_context(context)
        if command.expected_draft_updated_at.tzinfo is None:
            raise ScopeVersionValidationError("expected_draft_updated_at must include a timezone")
        if not command.idempotency_key.strip():
            raise ScopeVersionValidationError("Idempotency-Key must not be empty")
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        request_hash = self.request_hash(project_id, command.expected_draft_updated_at)
        now = datetime.now(UTC)
        scope_version_id: UUID | None = None
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                reservation = await unit_of_work.repository.reserve_create(
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    project_id=project_id,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    scope_version_id=self._id_factory(),
                    now=now,
                    expires_at=now + timedelta(hours=24),
                )
                scope_version_id = reservation.scope_version_id
                if not reservation.acquired:
                    if reservation.request_hash != request_hash:
                        raise ScopeVersionIdempotencyConflict
                    if reservation.response is None:
                        raise ScopeVersionRepositoryError
                    return reservation.response

                target = await unit_of_work.repository.get_freeze_target(
                    account_id=context.account_id,
                    project_id=project_id,
                )
                if target is None or target.draft is None:
                    raise ScopeVersionAccessNotFound
                draft = target.draft
                if draft.context_version != target.project_current_context_version:
                    raise ScopeVersionAccessNotFound
                if draft.updated_at != command.expected_draft_updated_at:
                    self._event_logger.emit(
                        "scope_version.version_conflict",
                        level="WARNING",
                        actor_id=str(context.subject_id),
                        context_version=draft.context_version,
                        status="conflict",
                        error_code="VERSION_CONFLICT",
                    )
                    raise ScopeVersionCreateConflict
                decision = self._readiness_policy.evaluate(
                    account_id=context.account_id,
                    project_id=project_id,
                    context_version=draft.context_version,
                    gaps=target.gaps,
                )
                if not decision.ready_for_share:
                    raise ScopeVersionNotReady
                snapshot_data = deepcopy(draft.content)
                snapshot_hash = hash_scope_snapshot(snapshot_data)
                if snapshot_hash == target.latest_snapshot_hash:
                    self._event_logger.emit(
                        "scope_version.unchanged_rejected",
                        level="WARNING",
                        actor_id=str(context.subject_id),
                        context_version=draft.context_version,
                        schema_version=snapshot_data["schema_version"],
                        status="rejected",
                        error_code="SCOPE_VERSION_UNCHANGED",
                    )
                    raise ScopeVersionUnchanged
                version = NewScopeVersion(
                    id=reservation.scope_version_id,
                    account_id=context.account_id,
                    project_id=project_id,
                    version_no=target.next_version_no,
                    context_version=draft.context_version,
                    status="awaiting_approval",
                    snapshot_data=snapshot_data,
                    snapshot_hash=snapshot_hash,
                    created_by=context.subject_id,
                )
                persisted = await unit_of_work.repository.add(version)
                await unit_of_work.repository.complete_create_reservation(
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    project_id=project_id,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    version=persisted,
                )
                await unit_of_work.commit()
        except ScopeVersionRepositoryError:
            fields: dict[str, object] = {
                "actor_id": str(context.subject_id),
                "component": "scope_version_repository",
                "operation": "create",
                "duration_ms": (perf_counter() - started_at) * 1000,
                "status": "failed",
                "error_code": "SCOPE_VERSION_CREATION_FAILURE",
            }
            if scope_version_id is not None:
                fields["scope_version_id"] = str(scope_version_id)
            self._event_logger.emit("scope_version.creation_failed", level="ERROR", **fields)
            raise
        self._event_logger.emit(
            "scope_version.created",
            actor_id=str(context.subject_id),
            scope_version_id=str(persisted.id),
            version_no=persisted.version_no,
            context_version=persisted.context_version,
            schema_version=persisted.snapshot_data["schema_version"],
            canonicalization_version=SCOPE_SNAPSHOT_CANONICALIZATION_VERSION,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        emit_product_analytics(
            self._event_logger,
            event_name="scope_version_saved",
            logical_id=persisted.id,
            account_id=persisted.account_id,
            project_id=persisted.project_id,
            actor_id=context.subject_id,
            properties={
                "context_version": persisted.context_version,
                "version_no": persisted.version_no,
            },
        )
        return persisted

    async def get(
        self, context: TenantContext, *, project_id: UUID, version_no: int
    ) -> ScopeVersion:
        _require_active_context(context)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        async with self._unit_of_work_factory() as unit_of_work:
            version = await unit_of_work.repository.get(
                account_id=context.account_id,
                project_id=project_id,
                version_no=version_no,
            )
        if version is None:
            raise ScopeVersionAccessNotFound
        return version

    async def list(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        limit: int,
        before_version_no: int | None,
    ) -> tuple[ScopeVersion, ...]:
        _require_active_context(context)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        async with self._unit_of_work_factory() as unit_of_work:
            versions = await unit_of_work.repository.list(
                account_id=context.account_id,
                project_id=project_id,
                limit=limit,
                before_version_no=before_version_no,
            )
            if versions is None:
                raise ScopeVersionAccessNotFound
            return versions


def _require_active_context(context: TenantContext) -> None:
    if context.membership_status != "active":
        raise ScopeVersionPermissionDenied
