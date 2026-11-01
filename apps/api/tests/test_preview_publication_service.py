"""Non-DB command-boundary checks; these do not prove persistence or tenant RLS."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from aria_backend_application.preview_delivery import PreviewError

from app.modules.generation.application.preview import (
    PreviewIssueResult,
    PreviewPublicationService,
    PreviewPublishResult,
)
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.identity.domain.membership import MembershipRole, MembershipStatus

NOW = datetime(2026, 10, 12, 10, tzinfo=UTC)
EXPIRY = NOW + timedelta(hours=1)  # Caller-specified synthetic test value, not a product default.


class RecordingCommands:
    def __init__(self) -> None:
        self.calls: list[tuple[str, TenantContext, dict[str, object]]] = []
        self.publication_id, self.job_id = uuid4(), uuid4()
        self.issue_result = PreviewIssueResult(self.publication_id, None, True)

    async def publish(self, context: TenantContext, **values: object) -> PreviewPublishResult:
        self.calls.append(("publish", context, values))
        return PreviewPublishResult(self.publication_id, self.job_id, False)

    async def issue(self, context: TenantContext, **values: object) -> PreviewIssueResult:
        self.calls.append(("issue", context, values))
        return self.issue_result

    async def revoke(self, context: TenantContext, **values: object) -> None:
        self.calls.append(("revoke", context, values))


def context() -> TenantContext:
    return TenantContext(uuid4(), uuid4(), uuid4(), "owner", "active")


async def invoke(
    service: PreviewPublicationService,
    actor: TenantContext,
    operation: str,
    *,
    key: str = "synthetic-command-key",
) -> None:
    if operation == "publish":
        await service.publish(actor, project_id=uuid4(), artifact_version_id=uuid4(), key=key)
    elif operation == "issue":
        await service.issue(
            actor, project_id=uuid4(), publication_id=uuid4(), key=key, expires_at=EXPIRY
        )
    else:
        await service.revoke(actor, project_id=uuid4(), publication_id=uuid4(), key=key)


@pytest.mark.parametrize("operation", ["publish", "issue", "revoke"])
@pytest.mark.parametrize("status", ["invited", "suspended"])
def test_inactive_membership_denied_before_command_port(
    operation: str, status: MembershipStatus
) -> None:
    commands = RecordingCommands()
    service = PreviewPublicationService(commands, synthetic_sources=frozenset(), clock=lambda: NOW)
    actor = replace(context(), membership_status=status)
    with pytest.raises(PreviewError, match="RESOURCE_NOT_FOUND"):
        asyncio.run(invoke(service, actor, operation))
    assert commands.calls == []


@pytest.mark.parametrize("operation", ["publish", "issue", "revoke"])
@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_active_role_reaches_port_without_inventing_resource_authorization(
    operation: str, role: MembershipRole
) -> None:
    commands = RecordingCommands()
    sources = frozenset({(uuid4(), "sha256:" + "1" * 64)})
    service = PreviewPublicationService(commands, synthetic_sources=sources, clock=lambda: NOW)
    actor = replace(context(), role=role)
    asyncio.run(invoke(service, actor, operation))
    assert len(commands.calls) == 1
    called, passed_actor, values = commands.calls[0]
    assert called == operation and passed_actor == actor and values["now"] == NOW
    if operation == "publish":
        assert values["synthetic_sources"] == sources
    # Ownership/source visibility is independently enforced by the Repository, not this stub.


@pytest.mark.parametrize("operation", ["publish", "issue", "revoke"])
@pytest.mark.parametrize("key", ["", " \t\n"])
def test_empty_idempotency_key_denied_before_command_port(operation: str, key: str) -> None:
    commands = RecordingCommands()
    service = PreviewPublicationService(commands, synthetic_sources=frozenset(), clock=lambda: NOW)
    with pytest.raises(PreviewError, match="VALIDATION_FAILED"):
        asyncio.run(invoke(service, context(), operation, key=key))
    assert commands.calls == []


def test_publish_fingerprint_binds_account_actor_project_version_and_operation() -> None:
    async def scenario() -> None:
        commands = RecordingCommands()
        service = PreviewPublicationService(
            commands, synthetic_sources=frozenset(), clock=lambda: NOW
        )
        actor, project, version = context(), uuid4(), uuid4()

        async def publish(
            current: TenantContext, target_project: UUID, target_version: UUID
        ) -> str:
            await service.publish(
                current,
                project_id=target_project,
                artifact_version_id=target_version,
                key="synthetic-command-key",
            )
            return str(commands.calls[-1][2]["request_hash"])

        original = await publish(actor, project, version)
        assert await publish(actor, project, version) == original
        changed = [
            await publish(replace(actor, account_id=uuid4()), project, version),
            await publish(replace(actor, subject_id=uuid4()), project, version),
            await publish(actor, uuid4(), version),
            await publish(actor, project, uuid4()),
        ]
        await service.revoke(
            actor, project_id=project, publication_id=version, key="synthetic-command-key"
        )
        changed.append(str(commands.calls[-1][2]["request_hash"]))
        assert len({original, *changed}) == 6

    asyncio.run(scenario())


def test_issue_fingerprint_normalizes_expiry_instant_and_distinguishes_changed_expiry() -> None:
    async def scenario() -> None:
        commands = RecordingCommands()
        service = PreviewPublicationService(
            commands, synthetic_sources=frozenset(), clock=lambda: NOW
        )
        actor, project, publication = context(), uuid4(), uuid4()
        hashes = []
        for expiry in (
            EXPIRY,
            EXPIRY.astimezone(timezone(timedelta(hours=3, minutes=30))),
            EXPIRY + timedelta(seconds=1),
        ):
            await service.issue(
                actor,
                project_id=project,
                publication_id=publication,
                key="synthetic-command-key",
                expires_at=expiry,
            )
            hashes.append(commands.calls[-1][2]["request_hash"])
        assert hashes[0] == hashes[1] and hashes[0] != hashes[2]

    asyncio.run(scenario())


def test_naive_expiry_rejected_before_command_port() -> None:
    commands = RecordingCommands()
    service = PreviewPublicationService(commands, synthetic_sources=frozenset(), clock=lambda: NOW)
    with pytest.raises(PreviewError, match="VALIDATION_FAILED"):
        asyncio.run(
            service.issue(
                context(),
                project_id=uuid4(),
                publication_id=uuid4(),
                key="synthetic-command-key",
                expires_at=EXPIRY.replace(tzinfo=None),
            )
        )
    assert commands.calls == []


def test_expired_original_expiry_reaches_replay_boundary_without_new_token() -> None:
    commands = RecordingCommands()
    service = PreviewPublicationService(
        commands, synthetic_sources=frozenset(), clock=lambda: EXPIRY + timedelta(seconds=1)
    )
    result = asyncio.run(
        service.issue(
            context(),
            project_id=uuid4(),
            publication_id=commands.publication_id,
            key="synthetic-command-key",
            expires_at=EXPIRY,
        )
    )
    assert result == commands.issue_result and result.replayed
    assert result.token is None and not result.token_available
    assert len(commands.calls) == 1
    # This proves delegation order only; real DB replay/no-second-issuance remains pending.


def test_one_time_token_is_explicit_result_only_and_absent_from_repr() -> None:
    marker = "synthetic-one-time-disclosure-marker"
    first = PreviewIssueResult(uuid4(), marker, False)
    replay = PreviewIssueResult(first.publication_id, None, True)
    assert first.token == marker and first.token_available
    assert marker not in repr(first) and marker not in str(first)
    assert not replay.token_available
    assert not hasattr(PreviewPublishResult(uuid4(), uuid4(), False), "token")


def test_unbounded_error_text_cannot_escape_as_public_preview_error() -> None:
    marker = "synthetic-content-token-url-marker"
    error = PreviewError(marker)
    assert error.code == "PREVIEW_SOURCE_INVALID"
    assert marker not in str(error) and marker not in repr(error)
