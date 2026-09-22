from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from aria_observability import current_trace_context
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, ValidationError
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.formparsers import MultiPartException

from app.api.dependencies.tenant_context import require_tenant_context
from app.api.errors import (
    ContextSourceBusyError,
    FeatureNotEnabledError,
    FileTooLargeApiError,
    IdempotencyConflictError,
    MembershipRequiredError,
    ResourceNotFoundError,
    StorageApiError,
    UnsupportedFileTypeApiError,
    ValidationFailedError,
)
from app.modules.context.application.context_source_management import (
    ContextSourceBusy,
    ContextSourceManagementService,
    ContextSourceNotFound,
    ContextSourceView,
)
from app.modules.context.application.file_context_ingestion import (
    CreateFileContextCommand,
    CreateFileContextUseCase,
    FileContextAccepted,
    FileContextIdempotencyConflict,
    FileContextNotFound,
    FileContextPermissionDenied,
    FileContextStorageFailure,
)
from app.modules.context.application.text_context_ingestion import (
    CreateTextContextCommand,
    CreateTextContextUseCase,
    TextContextAccepted,
    TextContextIdempotencyConflict,
    TextContextNotFound,
    TextContextPermissionDenied,
)
from app.modules.context.domain.context_source import ContextSourceValidationError
from app.modules.context.domain.file_upload import (
    TXT_UPLOAD_MAX_BYTES,
    FileTooLargeError,
    FileUploadValidationError,
    UnsupportedFileTypeError,
)
from app.modules.identity.application.tenant_context import TenantContext


class CreateTextContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["text"]
    raw_text: str


class ContextSourceAcceptedData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    status: Literal["uploaded"]
    job_id: UUID
    status_url: str


class ContextSourceAcceptedMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID


class ContextSourceAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ContextSourceAcceptedData
    meta: ContextSourceAcceptedMeta


class ContextSourceVersionSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    version_no: int
    parse_status: str
    created_at: datetime


class ContextSourceJobSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    status: str
    retryable: bool
    error_code: str | None
    status_url: str
    created_at: datetime


class ContextSourceSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    source_type: str
    status: str
    original_name: str | None
    mime_type: str | None
    created_at: datetime
    updated_at: datetime
    can_archive: bool
    latest_version: ContextSourceVersionSummaryResponse | None
    latest_job: ContextSourceJobSummaryResponse | None


class ContextSourceDetailResponse(ContextSourceSummaryResponse):
    current_ready_version: ContextSourceVersionSummaryResponse | None


class ContextSourceCollectionMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    next_cursor: str | None
    has_more: bool


class ContextSourcesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[ContextSourceSummaryResponse]
    meta: ContextSourceCollectionMeta


class ContextSourceDetailEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ContextSourceDetailResponse
    meta: ContextSourceAcceptedMeta


def _text_context_use_case(request: Request) -> CreateTextContextUseCase:
    return cast(CreateTextContextUseCase, request.app.state.text_context_use_case)


def _file_context_use_case(request: Request) -> CreateFileContextUseCase | None:
    return cast(CreateFileContextUseCase | None, request.app.state.file_context_use_case)


def _context_source_management_service(request: Request) -> ContextSourceManagementService:
    return cast(ContextSourceManagementService, request.app.state.context_source_management_service)


def create_context_sources_router(*, txt_upload_enabled: bool) -> APIRouter:
    router = APIRouter(prefix="/projects/{project_id}/context-sources", tags=["context"])

    @router.post(
        "",
        response_model=ContextSourceAcceptedResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_context_source(
        request: Request,
        project_id: UUID,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        text_use_case: Annotated[CreateTextContextUseCase, Depends(_text_context_use_case)],
        file_use_case: Annotated[
            CreateFileContextUseCase | None,
            Depends(_file_context_use_case),
        ],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> ContextSourceAcceptedResponse:
        trace = current_trace_context()
        if trace is None or trace.request_id is None:
            raise RuntimeError("Context Source ingestion requires an active request context")

        media_type = request.headers.get("content-type", "").split(";", maxsplit=1)[0].lower()
        accepted: TextContextAccepted | FileContextAccepted
        if media_type == "application/json":
            accepted = await _create_text_context(
                request=request,
                project_id=project_id,
                context=context,
                use_case=text_use_case,
                idempotency_key=idempotency_key,
                correlation_id=UUID(trace.correlation_id),
            )
        elif media_type == "multipart/form-data":
            if not txt_upload_enabled:
                raise FeatureNotEnabledError
            if file_use_case is None:
                raise RuntimeError("Enabled TXT upload requires configured object storage")
            accepted = await _create_file_context(
                request=request,
                project_id=project_id,
                context=context,
                use_case=file_use_case,
                idempotency_key=idempotency_key,
                correlation_id=UUID(trace.correlation_id),
            )
        else:
            raise ValidationFailedError

        return ContextSourceAcceptedResponse(
            data=ContextSourceAcceptedData(
                source_id=accepted.source_id,
                status="uploaded",
                job_id=accepted.job_id,
                status_url=f"/api/v1/jobs/{accepted.job_id}",
            ),
            meta=ContextSourceAcceptedMeta(request_id=UUID(trace.request_id)),
        )

    @router.get("", response_model=ContextSourcesResponse)
    async def list_context_sources(
        project_id: UUID,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[
            ContextSourceManagementService, Depends(_context_source_management_service)
        ],
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        cursor: str | None = None,
    ) -> ContextSourcesResponse:
        cursor_created_at, cursor_id = _decode_cursor(cursor)
        try:
            rows = await service.list(
                context,
                project_id=project_id,
                limit=limit + 1,
                cursor_created_at=cursor_created_at,
                cursor_id=cursor_id,
            )
        except ContextSourceNotFound:
            raise ResourceNotFoundError from None
        has_more = len(rows) > limit
        page = rows[:limit]
        trace = current_trace_context()
        if trace is None or trace.request_id is None:
            raise RuntimeError("Context Source list requires an active request context")
        return ContextSourcesResponse(
            data=[_source_summary(row) for row in page],
            meta=ContextSourceCollectionMeta(
                request_id=UUID(trace.request_id),
                next_cursor=_encode_cursor(page[-1]) if has_more and page else None,
                has_more=has_more,
            ),
        )

    @router.get("/{source_id}", response_model=ContextSourceDetailEnvelope)
    async def get_context_source(
        project_id: UUID,
        source_id: UUID,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[
            ContextSourceManagementService, Depends(_context_source_management_service)
        ],
    ) -> ContextSourceDetailEnvelope:
        try:
            row = await service.get(context, project_id=project_id, source_id=source_id)
        except ContextSourceNotFound:
            raise ResourceNotFoundError from None
        trace = current_trace_context()
        if trace is None or trace.request_id is None:
            raise RuntimeError("Context Source detail requires an active request context")
        summary = _source_summary(row)
        return ContextSourceDetailEnvelope(
            data=ContextSourceDetailResponse(
                **summary.model_dump(),
                current_ready_version=_version_response(row.current_ready_version),
            ),
            meta=ContextSourceAcceptedMeta(request_id=UUID(trace.request_id)),
        )

    @router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def archive_context_source(
        project_id: UUID,
        source_id: UUID,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[
            ContextSourceManagementService, Depends(_context_source_management_service)
        ],
    ) -> Response:
        try:
            await service.archive(context, project_id=project_id, source_id=source_id)
        except ContextSourceNotFound:
            raise ResourceNotFoundError from None
        except ContextSourceBusy:
            raise ContextSourceBusyError from None
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


def _source_summary(row: ContextSourceView) -> ContextSourceSummaryResponse:
    return ContextSourceSummaryResponse(
        id=row.id,
        source_type=row.source_type,
        status=row.status,
        original_name=row.original_name,
        mime_type=row.mime_type,
        created_at=row.created_at,
        updated_at=row.updated_at,
        can_archive=row.can_archive,
        latest_version=_version_response(row.latest_version),
        latest_job=(
            ContextSourceJobSummaryResponse(
                id=row.latest_job.id,
                status=row.latest_job.status,
                retryable=row.latest_job.retryable,
                error_code=row.latest_job.error_code,
                status_url=f"/api/v1/jobs/{row.latest_job.id}",
                created_at=row.latest_job.created_at,
            )
            if row.latest_job is not None
            else None
        ),
    )


def _version_response(value):
    if value is None:
        return None
    return ContextSourceVersionSummaryResponse(
        id=value.id,
        version_no=value.version_no,
        parse_status=value.parse_status,
        created_at=value.created_at,
    )


def _encode_cursor(row: ContextSourceView) -> str:
    raw = json.dumps(
        {"created_at": row.created_at.isoformat(), "id": str(row.id)},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(value: str | None) -> tuple[datetime | None, UUID | None]:
    if value is None:
        return None, None
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        created_at = datetime.fromisoformat(payload["created_at"])
        source_id = UUID(payload["id"])
        if created_at.tzinfo is None:
            raise ValueError
        return created_at, source_id
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise ValidationFailedError from None


async def _create_text_context(
    *,
    request: Request,
    project_id: UUID,
    context: TenantContext,
    use_case: CreateTextContextUseCase,
    idempotency_key: str,
    correlation_id: UUID,
) -> TextContextAccepted:
    try:
        body = CreateTextContextRequest.model_validate(await request.json())
        return await use_case.execute(
            context,
            CreateTextContextCommand(
                project_id=project_id,
                raw_text=body.raw_text,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            ),
        )
    except TextContextIdempotencyConflict:
        raise IdempotencyConflictError from None
    except TextContextNotFound:
        raise ResourceNotFoundError from None
    except TextContextPermissionDenied:
        raise MembershipRequiredError from None
    except (ContextSourceValidationError, ValidationError, ValueError, TypeError):
        raise ValidationFailedError from None


async def _create_file_context(
    *,
    request: Request,
    project_id: UUID,
    context: TenantContext,
    use_case: CreateFileContextUseCase,
    idempotency_key: str,
    correlation_id: UUID,
) -> FileContextAccepted:
    form = None
    try:
        form = await request.form(max_files=1, max_fields=1)
        parts = form.multi_items()
        if len(parts) != 2 or sorted(name for name, _ in parts) != ["file", "source_type"]:
            raise ValidationFailedError
        source_type = form.get("source_type")
        upload = form.get("file")
        if source_type != "file" or not isinstance(upload, UploadFile):
            raise ValidationFailedError
        if upload.size is not None and upload.size > TXT_UPLOAD_MAX_BYTES:
            raise FileTooLargeError
        content = await upload.read(TXT_UPLOAD_MAX_BYTES + 1)
        return await use_case.execute(
            context,
            CreateFileContextCommand(
                project_id=project_id,
                filename=upload.filename or "",
                declared_mime_type=upload.content_type,
                content=content,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            ),
        )
    except FileContextIdempotencyConflict:
        raise IdempotencyConflictError from None
    except FileContextNotFound:
        raise ResourceNotFoundError from None
    except FileContextPermissionDenied:
        raise MembershipRequiredError from None
    except UnsupportedFileTypeError:
        raise UnsupportedFileTypeApiError from None
    except FileTooLargeError:
        raise FileTooLargeApiError from None
    except FileContextStorageFailure as error:
        raise StorageApiError(retryable=error.retryable) from None
    except (
        FileUploadValidationError,
        MultiPartException,
        StarletteHTTPException,
        ValueError,
        TypeError,
    ):
        raise ValidationFailedError from None
    finally:
        if form is not None:
            await form.close()
