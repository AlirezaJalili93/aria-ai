from __future__ import annotations

import secrets
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text


class SignScopeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signer_name: str
    signer_role: str
    organization: str | None = None


class ScopeSignatureResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    scope_id: str
    signer_name: str
    signer_role: str
    organization: str | None
    verification_code: str
    signed_at: datetime


class CreateChangeRequestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requester_name: str
    requester_role: str
    category: str = "general"
    requested_changes: str


class ScopeChangeRequestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    scope_id: str
    requester_name: str
    requester_role: str
    category: str
    requested_changes: str
    status: str
    created_at: datetime


class ScopeChangeRequestsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[ScopeChangeRequestResponse]


def create_scope_signatures_router() -> APIRouter:
    router = APIRouter(prefix="/scopes/{scope_id}", tags=["scope-signatures"])

    @router.post(
        "/sign",
        response_model=ScopeSignatureResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def sign_scope(
        scope_id: str,
        body: SignScopeRequest,
        request: Request,
    ) -> ScopeSignatureResponse:
        session_factory = getattr(request.app.state, "session_factory", None)
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database session factory is unavailable.",
            )

        code_suffix = secrets.token_hex(3).upper()
        verification_code = f"SIG-ARIA-{scope_id[:8].upper()}-{code_suffix}"
        sig_id = uuid4()
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        select_sql = (
            "SELECT id, scope_id, signer_name, signer_role, "
            "organization, verification_code, signed_at "
            "FROM scope_signatures WHERE scope_id = :scope_id LIMIT 1"
        )
        insert_sql = (
            "INSERT INTO scope_signatures ("
            "id, scope_id, signer_name, signer_role, organization, "
            "verification_code, ip_address, user_agent) "
            "VALUES ("
            ":id, :scope_id, :signer_name, :signer_role, :organization, "
            ":verification_code, :ip_address, :user_agent) "
            "RETURNING id, scope_id, signer_name, signer_role, "
            "organization, verification_code, signed_at"
        )

        async with session_factory() as session:
            existing = (
                await session.execute(
                    text(select_sql),
                    {"scope_id": scope_id},
                )
            ).mappings().first()

            if existing:
                return ScopeSignatureResponse(
                    id=existing["id"],
                    scope_id=existing["scope_id"],
                    signer_name=existing["signer_name"],
                    signer_role=existing["signer_role"],
                    organization=existing["organization"],
                    verification_code=existing["verification_code"],
                    signed_at=existing["signed_at"],
                )

            result = (
                await session.execute(
                    text(insert_sql),
                    {
                        "id": sig_id,
                        "scope_id": scope_id,
                        "signer_name": body.signer_name.strip(),
                        "signer_role": body.signer_role.strip(),
                        "organization": (
                            body.organization.strip() if body.organization else None
                        ),
                        "verification_code": verification_code,
                        "ip_address": client_ip,
                        "user_agent": user_agent,
                    },
                )
            ).mappings().one()
            await session.commit()

            return ScopeSignatureResponse(
                id=result["id"],
                scope_id=result["scope_id"],
                signer_name=result["signer_name"],
                signer_role=result["signer_role"],
                organization=result["organization"],
                verification_code=result["verification_code"],
                signed_at=result["signed_at"],
            )

    @router.get("/signature", response_model=ScopeSignatureResponse | None)
    async def get_scope_signature(
        scope_id: str,
        request: Request,
    ) -> ScopeSignatureResponse | None:
        session_factory = getattr(request.app.state, "session_factory", None)
        if session_factory is None:
            return None

        select_sql = (
            "SELECT id, scope_id, signer_name, signer_role, "
            "organization, verification_code, signed_at "
            "FROM scope_signatures WHERE scope_id = :scope_id LIMIT 1"
        )

        async with session_factory() as session:
            existing = (
                await session.execute(
                    text(select_sql),
                    {"scope_id": scope_id},
                )
            ).mappings().first()

            if not existing:
                return None

            return ScopeSignatureResponse(
                id=existing["id"],
                scope_id=existing["scope_id"],
                signer_name=existing["signer_name"],
                signer_role=existing["signer_role"],
                organization=existing["organization"],
                verification_code=existing["verification_code"],
                signed_at=existing["signed_at"],
            )

    @router.post(
        "/change-requests",
        response_model=ScopeChangeRequestResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_change_request(
        scope_id: str,
        body: CreateChangeRequestPayload,
        request: Request,
    ) -> ScopeChangeRequestResponse:
        session_factory = getattr(request.app.state, "session_factory", None)
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database session factory is unavailable.",
            )

        req_id = uuid4()
        insert_sql = (
            "INSERT INTO scope_change_requests ("
            "id, scope_id, requester_name, requester_role, category, "
            "requested_changes, status) "
            "VALUES ("
            ":id, :scope_id, :requester_name, :requester_role, :category, "
            ":requested_changes, 'pending') "
            "RETURNING id, scope_id, requester_name, requester_role, "
            "category, requested_changes, status, created_at"
        )

        async with session_factory() as session:
            result = (
                await session.execute(
                    text(insert_sql),
                    {
                        "id": req_id,
                        "scope_id": scope_id,
                        "requester_name": body.requester_name.strip(),
                        "requester_role": body.requester_role.strip(),
                        "category": body.category.strip(),
                        "requested_changes": body.requested_changes.strip(),
                    },
                )
            ).mappings().one()
            await session.commit()

            return ScopeChangeRequestResponse(
                id=result["id"],
                scope_id=result["scope_id"],
                requester_name=result["requester_name"],
                requester_role=result["requester_role"],
                category=result["category"],
                requested_changes=result["requested_changes"],
                status=result["status"],
                created_at=result["created_at"],
            )

    @router.get(
        "/change-requests",
        response_model=ScopeChangeRequestsListResponse,
    )
    async def list_change_requests(
        scope_id: str,
        request: Request,
    ) -> ScopeChangeRequestsListResponse:
        session_factory = getattr(request.app.state, "session_factory", None)
        if session_factory is None:
            return ScopeChangeRequestsListResponse(data=[])

        select_sql = (
            "SELECT id, scope_id, requester_name, requester_role, "
            "category, requested_changes, status, created_at "
            "FROM scope_change_requests "
            "WHERE scope_id = :scope_id "
            "ORDER BY created_at DESC"
        )

        async with session_factory() as session:
            rows = (
                await session.execute(
                    text(select_sql),
                    {"scope_id": scope_id},
                )
            ).mappings().all()

            data = [
                ScopeChangeRequestResponse(
                    id=r["id"],
                    scope_id=r["scope_id"],
                    requester_name=r["requester_name"],
                    requester_role=r["requester_role"],
                    category=r["category"],
                    requested_changes=r["requested_changes"],
                    status=r["status"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]
            return ScopeChangeRequestsListResponse(data=data)

    return router
