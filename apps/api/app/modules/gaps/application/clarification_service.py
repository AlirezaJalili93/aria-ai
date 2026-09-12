from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from time import perf_counter
from uuid import UUID, uuid4

from aria_observability import StructuredEventLogger, enrich_trace_context

from app.modules.gaps.application.clarification_ports import (
    ClarificationRepositoryError,
    ClarificationUnitOfWork,
    ClarificationUnitOfWorkFactory,
    DuplicateClarificationRepositoryError,
)
from app.modules.gaps.domain.clarification import (
    Clarification,
    ClarificationAuthorType,
    ClarificationCreatorType,
    ClarificationResolution,
    ClarificationResolutionType,
    ClarificationStatus,
    NewClarification,
    NewClarificationResolution,
    normalize_question_text,
)
from app.modules.identity.application.tenant_context import TenantContext

QUESTION_CREATE_ROUTE_KEY = (
    "POST /api/v1/projects/{project_id}/gaps/{gap_id}/clarifications"
)
RESOLUTION_CREATE_ROUTE_KEY = (
    "POST /api/v1/projects/{project_id}/gaps/{gap_id}/"
    "clarifications/{clarification_id}/resolutions"
)
CLARIFICATION_IDEMPOTENCY_TTL = timedelta(hours=24)


class ClarificationNotFound(Exception):
    """The tenant-scoped Gap or Clarification was not found."""


class ClarificationPermissionDenied(Exception):
    """The caller does not have active Membership authority."""


class ClarificationInvalidState(Exception):
    """The Gap or Clarification is terminal for the requested command."""


class ClarificationVersionConflict(Exception):
    """The Clarification or Gap changed after the caller read it."""


class ClarificationDuplicate(Exception):
    """The same normalized open question already exists for the Gap."""


class ClarificationIdempotencyConflict(Exception):
    """An idempotency key was reused with different input."""


@dataclass(frozen=True, slots=True)
class CreateClarificationQuestionCommand:
    question_text: str
    idempotency_key: str
    created_by_type: ClarificationCreatorType = "user"


@dataclass(frozen=True, slots=True)
class EditClarificationQuestionCommand:
    question_text: str
    expected_updated_at: datetime


@dataclass(frozen=True, slots=True)
class ResolveClarificationCommand:
    resolution_type: ClarificationResolutionType
    answer_text: str | None
    author_type: ClarificationAuthorType
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class DismissGapCommand:
    expected_updated_at: datetime


class ClarificationService:
    def __init__(
        self,
        unit_of_work_factory: ClarificationUnitOfWorkFactory,
        event_logger: StructuredEventLogger,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger
        self._id_factory = id_factory
        self._clock = clock

    async def create_question(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        gap_id: UUID,
        command: CreateClarificationQuestionCommand,
    ) -> Clarification:
        _require_active_context(context)
        if not command.idempotency_key.strip():
            raise ValueError("Idempotency-Key must not be empty")
        normalized = normalize_question_text(command.question_text)
        created_by = context.subject_id if command.created_by_type == "user" else None
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        now = self._clock()
        request_hash = _hash_payload(
            {
                "project_id": str(project_id),
                "gap_id": str(gap_id),
                "question_text": normalized,
                "created_by_type": command.created_by_type,
            }
        )
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                reservation = await unit_of_work.idempotency.reserve(
                    record_id=self._id_factory(),
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=QUESTION_CREATE_ROUTE_KEY,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    now=now,
                    expires_at=now + CLARIFICATION_IDEMPOTENCY_TTL,
                )
                if not reservation.acquired:
                    if reservation.request_hash != request_hash:
                        raise ClarificationIdempotencyConflict
                    return await self._replay_question(
                        unit_of_work,
                        context=context,
                        project_id=project_id,
                        gap_id=gap_id,
                        response_status=reservation.response_status,
                        response_ref=reservation.response_ref,
                    )
                gap = await unit_of_work.repository.get_gap_for_update(
                    account_id=context.account_id, project_id=project_id, gap_id=gap_id
                )
                if gap is None:
                    self._access_denied(context, project_id, gap_id)
                    raise ClarificationNotFound
                if gap.status != "open":
                    raise ClarificationInvalidState
                persisted = await unit_of_work.repository.add_question(
                    NewClarification(
                        id=self._id_factory(),
                        account_id=context.account_id,
                        project_id=project_id,
                        gap_id=gap_id,
                        question_text=normalized,
                        created_by_type=command.created_by_type,
                        created_by=created_by,
                    )
                )
                await unit_of_work.idempotency.complete(
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=QUESTION_CREATE_ROUTE_KEY,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    response_status=201,
                    response_ref={"clarification_id": str(persisted.id)},
                )
                await unit_of_work.commit()
        except DuplicateClarificationRepositoryError:
            self._event_logger.emit(
                "clarification.duplicate_rejected",
                level="WARNING",
                actor_id=str(context.subject_id),
                gap_id=str(gap_id),
                duration_ms=(perf_counter() - started_at) * 1000,
                status="rejected",
                reason_code="exact_open_question",
            )
            raise ClarificationDuplicate from None
        except ClarificationRepositoryError:
            self._repository_failed("create_question", context, started_at)
            raise
        self._event_logger.emit(
            "clarification.created",
            actor_id=str(context.subject_id),
            gap_id=str(gap_id),
            clarification_id=str(persisted.id),
            created_by_type=persisted.created_by_type,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return persisted

    async def edit_question(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        gap_id: UUID,
        clarification_id: UUID,
        command: EditClarificationQuestionCommand,
    ) -> Clarification:
        _require_active_context(context)
        if command.expected_updated_at.tzinfo is None:
            raise ValueError("expected_updated_at must include a timezone")
        normalized = normalize_question_text(command.question_text)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                gap = await unit_of_work.repository.get_gap_for_update(
                    account_id=context.account_id, project_id=project_id, gap_id=gap_id
                )
                if gap is None:
                    self._access_denied(context, project_id, gap_id, clarification_id)
                    raise ClarificationNotFound
                current = await unit_of_work.repository.get_question_for_update(
                    account_id=context.account_id,
                    project_id=project_id,
                    gap_id=gap_id,
                    clarification_id=clarification_id,
                )
                if current is None:
                    self._access_denied(context, project_id, gap_id, clarification_id)
                    raise ClarificationNotFound
                if gap.status != "open" or current.status != "open":
                    raise ClarificationInvalidState
                if current.updated_at != command.expected_updated_at:
                    self._version_conflict(context, gap_id, clarification_id)
                    raise ClarificationVersionConflict
                if current.question_text == normalized:
                    return current
                persisted = await unit_of_work.repository.update_question_text(
                    account_id=context.account_id,
                    project_id=project_id,
                    gap_id=gap_id,
                    clarification_id=clarification_id,
                    expected_updated_at=command.expected_updated_at,
                    question_text=normalized,
                )
                if persisted is None:
                    self._version_conflict(context, gap_id, clarification_id)
                    raise ClarificationVersionConflict
                await unit_of_work.commit()
        except DuplicateClarificationRepositoryError:
            self._event_logger.emit(
                "clarification.duplicate_rejected",
                level="WARNING",
                actor_id=str(context.subject_id),
                gap_id=str(gap_id),
                clarification_id=str(clarification_id),
                duration_ms=(perf_counter() - started_at) * 1000,
                status="rejected",
                reason_code="exact_open_question",
            )
            raise ClarificationDuplicate from None
        except ClarificationRepositoryError:
            self._repository_failed("edit_question", context, started_at)
            raise
        self._event_logger.emit(
            "clarification.edited",
            actor_id=str(context.subject_id),
            gap_id=str(gap_id),
            clarification_id=str(clarification_id),
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return persisted

    async def resolve_question(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        gap_id: UUID,
        clarification_id: UUID,
        command: ResolveClarificationCommand,
    ) -> ClarificationResolution:
        _require_active_context(context)
        if not command.idempotency_key.strip():
            raise ValueError("Idempotency-Key must not be empty")
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        now = self._clock()
        validated = NewClarificationResolution(
            id=self._id_factory(),
            account_id=context.account_id,
            project_id=project_id,
            gap_id=gap_id,
            clarification_id=clarification_id,
            resolution_type=command.resolution_type,
            answer_text=command.answer_text,
            author_type=command.author_type,
            author_id=context.subject_id if command.author_type == "user" else None,
            actor_id=context.subject_id,
        )
        request_hash = _hash_payload(
            {
                "project_id": str(project_id),
                "gap_id": str(gap_id),
                "clarification_id": str(clarification_id),
                "resolution_type": validated.resolution_type,
                "answer_text": validated.answer_text,
                "author_type": validated.author_type,
            }
        )
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                reservation = await unit_of_work.idempotency.reserve(
                    record_id=self._id_factory(),
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=RESOLUTION_CREATE_ROUTE_KEY,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    now=now,
                    expires_at=now + CLARIFICATION_IDEMPOTENCY_TTL,
                )
                if not reservation.acquired:
                    if reservation.request_hash != request_hash:
                        raise ClarificationIdempotencyConflict
                    return await self._replay_resolution(
                        unit_of_work,
                        context=context,
                        project_id=project_id,
                        gap_id=gap_id,
                        response_status=reservation.response_status,
                        response_ref=reservation.response_ref,
                    )
                gap = await unit_of_work.repository.get_gap_for_update(
                    account_id=context.account_id, project_id=project_id, gap_id=gap_id
                )
                if gap is None:
                    self._access_denied(context, project_id, gap_id, clarification_id)
                    raise ClarificationNotFound
                current = await unit_of_work.repository.get_question_for_update(
                    account_id=context.account_id,
                    project_id=project_id,
                    gap_id=gap_id,
                    clarification_id=clarification_id,
                )
                if current is None:
                    self._access_denied(context, project_id, gap_id, clarification_id)
                    raise ClarificationNotFound
                if gap.status != "open" or current.status != "open":
                    raise ClarificationInvalidState
                persisted = await unit_of_work.repository.add_resolution(validated)
                target_status: ClarificationStatus = (
                    "ignored" if validated.resolution_type == "ignored" else "answered"
                )
                await unit_of_work.repository.set_question_status(
                    account_id=context.account_id,
                    project_id=project_id,
                    gap_id=gap_id,
                    clarification_id=clarification_id,
                    status=target_status,
                )
                gap_resolved = False
                if not await unit_of_work.repository.has_open_questions(
                    account_id=context.account_id, project_id=project_id, gap_id=gap_id
                ):
                    updated_gap = await unit_of_work.repository.set_gap_status(
                        account_id=context.account_id,
                        project_id=project_id,
                        gap_id=gap_id,
                        expected_updated_at=gap.updated_at,
                        status="resolved",
                        resolved_at=now,
                    )
                    if updated_gap is None:
                        raise ClarificationVersionConflict
                    gap_resolved = True
                await unit_of_work.idempotency.complete(
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=RESOLUTION_CREATE_ROUTE_KEY,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    response_status=201,
                    response_ref={"resolution_id": str(persisted.id)},
                )
                await unit_of_work.commit()
        except ClarificationRepositoryError:
            self._repository_failed("resolve_question", context, started_at)
            raise
        event_name = (
            "clarification.ignored"
            if persisted.resolution_type == "ignored"
            else "clarification.answered"
        )
        self._event_logger.emit(
            event_name,
            actor_id=str(context.subject_id),
            gap_id=str(gap_id),
            clarification_id=str(clarification_id),
            resolution_type=persisted.resolution_type,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        if gap_resolved:
            self._event_logger.emit(
                "gap.resolved",
                actor_id=str(context.subject_id),
                gap_id=str(gap_id),
                clarification_id=str(clarification_id),
                duration_ms=(perf_counter() - started_at) * 1000,
                status="resolved",
            )
        return persisted

    async def dismiss_gap(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        gap_id: UUID,
        command: DismissGapCommand,
    ) -> None:
        _require_active_context(context)
        if command.expected_updated_at.tzinfo is None:
            raise ValueError("expected_updated_at must include a timezone")
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                gap = await unit_of_work.repository.get_gap_for_update(
                    account_id=context.account_id, project_id=project_id, gap_id=gap_id
                )
                if gap is None:
                    self._access_denied(context, project_id, gap_id)
                    raise ClarificationNotFound
                if gap.status != "open":
                    raise ClarificationInvalidState
                if gap.updated_at != command.expected_updated_at:
                    self._version_conflict(context, gap_id)
                    raise ClarificationVersionConflict
                persisted = await unit_of_work.repository.set_gap_status(
                    account_id=context.account_id,
                    project_id=project_id,
                    gap_id=gap_id,
                    expected_updated_at=command.expected_updated_at,
                    status="dismissed",
                    resolved_at=None,
                )
                if persisted is None:
                    self._version_conflict(context, gap_id)
                    raise ClarificationVersionConflict
                await unit_of_work.commit()
        except ClarificationRepositoryError:
            self._repository_failed("dismiss_gap", context, started_at)
            raise
        self._event_logger.emit(
            "gap.dismissed",
            actor_id=str(context.subject_id),
            gap_id=str(gap_id),
            duration_ms=(perf_counter() - started_at) * 1000,
            status="dismissed",
        )

    async def _replay_question(
        self,
        unit_of_work: ClarificationUnitOfWork,
        *,
        context: TenantContext,
        project_id: UUID,
        gap_id: UUID,
        response_status: int | None,
        response_ref: dict[str, object] | None,
    ) -> Clarification:
        try:
            if response_status != 201 or response_ref is None:
                raise ValueError
            clarification_id = UUID(str(response_ref["clarification_id"]))
        except (KeyError, TypeError, ValueError):
            raise ClarificationRepositoryError from None
        existing = await unit_of_work.repository.get_question_by_id(
            account_id=context.account_id,
            project_id=project_id,
            gap_id=gap_id,
            clarification_id=clarification_id,
        )
        if existing is None:
            raise ClarificationRepositoryError
        return existing

    async def _replay_resolution(
        self,
        unit_of_work: ClarificationUnitOfWork,
        *,
        context: TenantContext,
        project_id: UUID,
        gap_id: UUID,
        response_status: int | None,
        response_ref: dict[str, object] | None,
    ) -> ClarificationResolution:
        try:
            if response_status != 201 or response_ref is None:
                raise ValueError
            resolution_id = UUID(str(response_ref["resolution_id"]))
        except (KeyError, TypeError, ValueError):
            raise ClarificationRepositoryError from None
        existing = await unit_of_work.repository.get_resolution_by_id(
            account_id=context.account_id,
            project_id=project_id,
            gap_id=gap_id,
            resolution_id=resolution_id,
        )
        if existing is None:
            raise ClarificationRepositoryError
        return existing

    def _version_conflict(
        self,
        context: TenantContext,
        gap_id: UUID,
        clarification_id: UUID | None = None,
    ) -> None:
        fields: dict[str, object] = {
            "actor_id": str(context.subject_id),
            "gap_id": str(gap_id),
            "status": "conflict",
            "error_code": "VERSION_CONFLICT",
        }
        if clarification_id is not None:
            fields["clarification_id"] = str(clarification_id)
        self._event_logger.emit("clarification.version_conflict", level="WARNING", **fields)

    def _access_denied(
        self,
        context: TenantContext,
        project_id: UUID,
        gap_id: UUID,
        clarification_id: UUID | None = None,
    ) -> None:
        fields: dict[str, object] = {
            "actor_id": str(context.subject_id),
            "project_id": str(project_id),
            "gap_id": str(gap_id),
            "status": "denied",
            "error_code": "RESOURCE_NOT_FOUND",
        }
        if clarification_id is not None:
            fields["clarification_id"] = str(clarification_id)
        self._event_logger.emit(
            "security.clarification_access_denied", level="WARNING", **fields
        )

    def _repository_failed(
        self, operation: str, context: TenantContext, started_at: float
    ) -> None:
        self._event_logger.emit(
            "clarification.repository_failed",
            level="ERROR",
            actor_id=str(context.subject_id),
            component="clarification_repository",
            operation=operation,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="failed",
            error_code="CLARIFICATION_REPOSITORY_FAILURE",
        )


def _require_active_context(context: TenantContext) -> None:
    if context.membership_status != "active":
        raise ClarificationPermissionDenied


def _hash_payload(value: dict[str, object]) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return sha256(canonical).hexdigest()
