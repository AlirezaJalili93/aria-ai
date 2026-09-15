from __future__ import annotations

from typing import Annotated, Literal, cast
from uuid import UUID

from aria_observability import current_trace_context
from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, ConfigDict, ValidationError
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.formparsers import MultiPartException

from app.api.dependencies.tenant_context import require_tenant_context
from app.api.errors import (
    FeatureNotEnabledError,
    FileTooLargeApiError,
    IdempotencyConflictError,
    MembershipRequiredError,
    ResourceNotFoundError,
    StorageApiError,
    UnsupportedFileTypeApiError,
    ValidationFailedError,
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


def _text_context_use_case(request: Request) -> CreateTextContextUseCase:
    return cast(CreateTextContextUseCase, request.app.state.text_context_use_case)


def _file_context_use_case(request: Request) -> CreateFileContextUseCase | None:
    return cast(CreateFileContextUseCase | None, request.app.state.file_context_use_case)


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

    return router


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
