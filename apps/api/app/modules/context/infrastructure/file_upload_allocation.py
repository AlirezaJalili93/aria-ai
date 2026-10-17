from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.context.application.file_upload_ports import (
    FileUploadAllocation,
    NewFileUploadAllocation,
    UploadAllocationStatus,
)
from app.modules.context.infrastructure.models import FileUploadAllocationModel


class SqlAlchemyFileUploadAllocationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def allocate_or_get(
        self,
        allocation: NewFileUploadAllocation,
        *,
        now: datetime,
    ) -> FileUploadAllocation:
        scope = (
            FileUploadAllocationModel.account_id == allocation.account_id,
            FileUploadAllocationModel.actor_id == allocation.actor_id,
            FileUploadAllocationModel.project_id == allocation.project_id,
            FileUploadAllocationModel.idempotency_key == allocation.idempotency_key,
        )
        await self._session.execute(
            delete(FileUploadAllocationModel).where(
                *scope,
                FileUploadAllocationModel.status == "committed",
                FileUploadAllocationModel.expires_at <= now,
            )
        )
        inserted = await self._session.scalar(
            insert(FileUploadAllocationModel)
            .values(
                id=allocation.id,
                account_id=allocation.account_id,
                actor_id=allocation.actor_id,
                project_id=allocation.project_id,
                idempotency_key=allocation.idempotency_key,
                request_hash=allocation.request_hash,
                source_id=allocation.source_id,
                source_version_id=allocation.source_version_id,
                job_id=allocation.job_id,
                object_key=allocation.object_key,
                status="allocated",
                expires_at=allocation.expires_at,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    "account_id",
                    "actor_id",
                    "project_id",
                    "idempotency_key",
                ]
            )
            .returning(FileUploadAllocationModel)
        )
        if inserted is not None:
            return _from_model(inserted)

        existing = await self._session.scalar(
            select(FileUploadAllocationModel).where(*scope)
        )
        if existing is None:
            raise RuntimeError("Upload allocation conflict could not be resolved")
        return _from_model(existing)

    async def get(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        project_id: UUID,
        idempotency_key: str,
    ) -> FileUploadAllocation | None:
        model = await self._session.scalar(
            select(FileUploadAllocationModel).where(
                FileUploadAllocationModel.account_id == account_id,
                FileUploadAllocationModel.actor_id == actor_id,
                FileUploadAllocationModel.project_id == project_id,
                FileUploadAllocationModel.idempotency_key == idempotency_key,
            )
        )
        return _from_model(model) if model is not None else None

    async def transition(
        self,
        *,
        allocation_id: UUID,
        expected_status: UploadAllocationStatus,
        status: UploadAllocationStatus,
        now: datetime,
        response_status: int | None = None,
    ) -> bool:
        updated_id = await self._session.scalar(
            update(FileUploadAllocationModel)
            .where(
                FileUploadAllocationModel.id == allocation_id,
                FileUploadAllocationModel.status == expected_status,
            )
            .values(
                status=status,
                response_status=response_status,
                updated_at=now,
            )
            .returning(FileUploadAllocationModel.id)
        )
        return updated_id is not None


def _from_model(model: FileUploadAllocationModel) -> FileUploadAllocation:
    return FileUploadAllocation(
        id=model.id,
        account_id=model.account_id,
        actor_id=model.actor_id,
        project_id=model.project_id,
        idempotency_key=model.idempotency_key,
        request_hash=model.request_hash,
        source_id=model.source_id,
        source_version_id=model.source_version_id,
        job_id=model.job_id,
        object_key=model.object_key,
        status=cast(UploadAllocationStatus, model.status),
        response_status=model.response_status,
        expires_at=model.expires_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
