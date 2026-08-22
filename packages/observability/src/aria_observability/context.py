from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from uuid import UUID, uuid4

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def _uuid_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a UUID string")
    try:
        return str(UUID(value))
    except ValueError:
        raise ValueError(f"{field_name} must be a UUID string") from None


def _optional_uuid_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _uuid_string(value, field_name)


def _safe_identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a safe identifier")
    if _SAFE_IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a safe identifier")
    return value


def _safe_or_generated_uuid(value: str | None) -> str:
    if value is not None:
        try:
            return str(UUID(value))
        except ValueError:
            pass
    return str(uuid4())


@dataclass(frozen=True, slots=True)
class TraceContext:
    correlation_id: str
    request_id: str | None = None
    account_id: str | None = None
    project_id: str | None = None
    job_id: str | None = None


_TRACE_CONTEXT: ContextVar[TraceContext | None] = ContextVar(
    "aria_trace_context", default=None
)


def current_trace_context() -> TraceContext | None:
    return _TRACE_CONTEXT.get()


def enrich_trace_context(
    *,
    account_id: str | None = None,
    project_id: str | None = None,
    job_id: str | None = None,
) -> TraceContext:
    """Add validated identifiers to the current trace in the active execution context.

    Callers may attach account or project identifiers only after the corresponding tenant
    authorization has succeeded. This function validates identifiers; authorization remains an
    Application/API responsibility.
    """
    context = current_trace_context()
    if context is None:
        raise RuntimeError("An active trace context is required for enrichment")
    if account_id is None and project_id is None and job_id is None:
        raise ValueError("At least one trace identifier is required for enrichment")

    enriched = replace(
        context,
        account_id=(
            _uuid_string(account_id, "account_id")
            if account_id is not None
            else context.account_id
        ),
        project_id=(
            _uuid_string(project_id, "project_id")
            if project_id is not None
            else context.project_id
        ),
        job_id=_uuid_string(job_id, "job_id") if job_id is not None else context.job_id,
    )
    _TRACE_CONTEXT.set(enriched)
    return enriched


@contextmanager
def bind_trace_context(context: TraceContext) -> Iterator[None]:
    token = _TRACE_CONTEXT.set(context)
    try:
        yield
    finally:
        _TRACE_CONTEXT.reset(token)


def resolve_http_trace_context(
    request_id: str | None,
    correlation_id: str | None,
) -> TraceContext:
    return TraceContext(
        request_id=_safe_or_generated_uuid(request_id),
        correlation_id=_safe_or_generated_uuid(correlation_id),
    )


@dataclass(frozen=True, slots=True)
class ProviderTraceContext:
    correlation_id: str
    job_id: str


@dataclass(frozen=True, slots=True)
class JobTraceContext:
    job_id: str
    task_type: str
    payload_version: str
    account_id: str
    project_id: str | None
    correlation_id: str

    @classmethod
    def from_current_request(
        cls,
        *,
        job_id: str,
        task_type: str,
        payload_version: str,
        account_id: str,
        project_id: str | None,
    ) -> JobTraceContext:
        request_context = current_trace_context()
        if request_context is None:
            raise RuntimeError("A request trace context is required to create a job context")
        return cls(
            job_id=_uuid_string(job_id, "job_id"),
            task_type=_safe_identifier(task_type, "task_type"),
            payload_version=_safe_identifier(payload_version, "payload_version"),
            account_id=_uuid_string(account_id, "account_id"),
            project_id=_optional_uuid_string(project_id, "project_id"),
            correlation_id=request_context.correlation_id,
        )

    @classmethod
    def from_message_context(cls, value: Mapping[str, object]) -> JobTraceContext:
        return cls(
            job_id=_uuid_string(value.get("jobId"), "jobId"),
            task_type=_safe_identifier(value.get("taskType"), "taskType"),
            payload_version=_safe_identifier(
                value.get("payloadVersion"), "payloadVersion"
            ),
            account_id=_uuid_string(value.get("accountId"), "accountId"),
            project_id=_optional_uuid_string(value.get("projectId"), "projectId"),
            correlation_id=_uuid_string(value.get("correlationId"), "correlationId"),
        )

    def to_message_context(self) -> dict[str, str | None]:
        return {
            "jobId": self.job_id,
            "taskType": self.task_type,
            "payloadVersion": self.payload_version,
            "accountId": self.account_id,
            "projectId": self.project_id,
            "correlationId": self.correlation_id,
        }

    def to_trace_context(self) -> TraceContext:
        return TraceContext(
            correlation_id=self.correlation_id,
            account_id=self.account_id,
            project_id=self.project_id,
            job_id=self.job_id,
        )

    def to_provider_context(self) -> ProviderTraceContext:
        return ProviderTraceContext(correlation_id=self.correlation_id, job_id=self.job_id)
