from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from app.modules.identity.application.membership_ports import (
    MembershipProjectionInvariantError,
    ResolvedMembership,
)
from app.modules.identity.application.membership_resolution import (
    ActiveMembershipRequired,
    ResolveActiveMembershipUseCase,
)
from app.modules.identity.application.ports import AuthenticatedIdentity
from app.modules.identity.domain.membership import MembershipRole, MembershipStatus


@dataclass
class MemoryMembershipRepository:
    memberships: tuple[ResolvedMembership, ...]
    calls: list[tuple[UUID, UUID]]

    async def resolve_membership(
        self,
        *,
        user_id: UUID,
        account_id: UUID,
    ) -> ResolvedMembership | None:
        self.calls.append((user_id, account_id))
        return next(
            (
                membership
                for membership in self.memberships
                if membership.user_id == user_id and membership.account_id == account_id
            ),
            None,
        )


def _membership(
    *,
    user_id: UUID,
    account_id: UUID,
    role: MembershipRole = "member",
    status: MembershipStatus = "active",
) -> ResolvedMembership:
    return ResolvedMembership(
        membership_id=uuid4(),
        account_id=account_id,
        user_id=user_id,
        role=role,
        status=status,
    )


def test_selects_requested_account_from_multiple_active_memberships() -> None:
    subject = uuid4()
    first_account = uuid4()
    selected_account = uuid4()
    selected_membership = _membership(
        user_id=subject,
        account_id=selected_account,
        role="admin",
    )
    repository = MemoryMembershipRepository(
        memberships=(
            _membership(user_id=subject, account_id=first_account, role="owner"),
            selected_membership,
        ),
        calls=[],
    )
    use_case = ResolveActiveMembershipUseCase(repository)

    context = asyncio.run(
        use_case.execute(AuthenticatedIdentity(subject=subject), selected_account)
    )

    assert context.subject == subject
    assert context.account_id == selected_account
    assert context.membership == selected_membership
    assert context.membership.role == "admin"
    assert repository.calls == [(subject, selected_account)]


@pytest.mark.parametrize("status", ["invited", "suspended"])
def test_inactive_membership_cannot_be_selected(status: MembershipStatus) -> None:
    subject = uuid4()
    account_id = uuid4()
    repository = MemoryMembershipRepository(
        memberships=(_membership(user_id=subject, account_id=account_id, status=status),),
        calls=[],
    )

    with pytest.raises(ActiveMembershipRequired) as captured:
        asyncio.run(
            ResolveActiveMembershipUseCase(repository).execute(
                AuthenticatedIdentity(subject=subject),
                account_id,
            )
        )
    assert captured.value.reason_code == status


def test_account_without_membership_is_denied() -> None:
    subject = uuid4()
    requested_account = uuid4()
    repository = MemoryMembershipRepository(
        memberships=(_membership(user_id=subject, account_id=uuid4()),),
        calls=[],
    )

    with pytest.raises(ActiveMembershipRequired) as captured:
        asyncio.run(
            ResolveActiveMembershipUseCase(repository).execute(
                AuthenticatedIdentity(subject=subject),
                requested_account,
            )
        )

    assert captured.value.reason_code == "not_found"

    assert repository.calls == [(subject, requested_account)]


def test_other_users_membership_cannot_authorize_requested_account() -> None:
    subject = uuid4()
    requested_account = uuid4()
    repository = MemoryMembershipRepository(
        memberships=(_membership(user_id=uuid4(), account_id=requested_account),),
        calls=[],
    )

    with pytest.raises(ActiveMembershipRequired) as captured:
        asyncio.run(
            ResolveActiveMembershipUseCase(repository).execute(
                AuthenticatedIdentity(subject=subject),
                requested_account,
            )
        )
    assert captured.value.reason_code == "not_found"


def test_mismatched_repository_result_fails_closed() -> None:
    subject = uuid4()
    requested_account = uuid4()

    class MismatchedRepository:
        async def resolve_membership(
            self,
            *,
            user_id: UUID,
            account_id: UUID,
        ) -> ResolvedMembership:
            del user_id, account_id
            return _membership(user_id=uuid4(), account_id=requested_account)

    with pytest.raises(MembershipProjectionInvariantError):
        asyncio.run(
            ResolveActiveMembershipUseCase(MismatchedRepository()).execute(
                AuthenticatedIdentity(subject=subject),
                requested_account,
            )
        )
