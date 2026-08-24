from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from app.modules.identity.application.account_bootstrap import (
    ActiveMembershipRequired,
    BootstrapAccountUseCase,
)
from app.modules.identity.application.bootstrap_ports import (
    AccountBootstrapRepository,
    ResolvedMembership,
)
from app.modules.identity.application.ports import AuthenticatedIdentity


@dataclass
class MemoryState:
    profiles: set[UUID] = field(default_factory=set)
    accounts: set[UUID] = field(default_factory=set)
    memberships: dict[UUID, ResolvedMembership] = field(default_factory=dict)
    writes: int = 0
    profile_gate: asyncio.Lock = field(default_factory=asyncio.Lock)


class MemoryRepository(AccountBootstrapRepository):
    def __init__(self, state: MemoryState, *, fail_membership_insert: bool = False) -> None:
        self._state = state
        self._fail_membership_insert = fail_membership_insert

    async def resolve_memberships(self, user_id: UUID) -> tuple[ResolvedMembership, ...]:
        return tuple(
            membership
            for membership in self._state.memberships.values()
            if membership.user_id == user_id
        )

    async def create_profile_if_absent(self, user_id: UUID) -> bool:
        async with self._state.profile_gate:
            if user_id in self._state.profiles:
                return False
            self._state.profiles.add(user_id)
            self._state.writes += 1
            return True

    async def add_account(self, account_id: UUID) -> None:
        self._state.accounts.add(account_id)
        self._state.writes += 1

    async def add_owner_membership(
        self,
        *,
        membership_id: UUID,
        account_id: UUID,
        user_id: UUID,
    ) -> None:
        if self._fail_membership_insert:
            raise RuntimeError("injected membership failure")
        self._state.memberships[membership_id] = ResolvedMembership(
            membership_id=membership_id,
            account_id=account_id,
            user_id=user_id,
            role="owner",
            status="active",
        )
        self._state.writes += 1


class MemoryUnitOfWork:
    def __init__(self, state: MemoryState, *, fail_membership_insert: bool = False) -> None:
        self._state = state
        self.repository = MemoryRepository(
            state,
            fail_membership_insert=fail_membership_insert,
        )
        self._snapshot: MemoryState | None = None
        self._committed = False

    async def __aenter__(self) -> MemoryUnitOfWork:
        self._snapshot = deepcopy(self._state)
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        if not self._committed and self._snapshot is not None:
            self._state.profiles = self._snapshot.profiles
            self._state.accounts = self._snapshot.accounts
            self._state.memberships = self._snapshot.memberships
            self._state.writes = self._snapshot.writes

    async def commit(self) -> None:
        self._committed = True


class MemoryUnitOfWorkFactory:
    def __init__(self, state: MemoryState, *, fail_membership_insert: bool = False) -> None:
        self._state = state
        self._fail_membership_insert = fail_membership_insert

    def __call__(self) -> MemoryUnitOfWork:
        return MemoryUnitOfWork(
            self._state,
            fail_membership_insert=self._fail_membership_insert,
        )


def test_first_request_creates_profile_account_and_active_owner_membership() -> None:
    state = MemoryState()
    subject = uuid4()
    use_case = BootstrapAccountUseCase(MemoryUnitOfWorkFactory(state))

    context = asyncio.run(use_case.execute(AuthenticatedIdentity(subject=subject)))

    assert context.subject == subject
    assert context.created is True
    assert len(context.active_memberships) == 1
    assert context.active_memberships[0].role == "owner"
    assert context.active_memberships[0].status == "active"
    assert state.profiles == {subject}
    assert len(state.accounts) == 1
    assert len(state.memberships) == 1


def test_repeated_request_resolves_existing_context_without_writes() -> None:
    state = MemoryState()
    subject = uuid4()
    use_case = BootstrapAccountUseCase(MemoryUnitOfWorkFactory(state))
    first = asyncio.run(use_case.execute(AuthenticatedIdentity(subject=subject)))
    writes_after_first = state.writes

    second = asyncio.run(use_case.execute(AuthenticatedIdentity(subject=subject)))

    assert second.created is False
    assert second.active_memberships == first.active_memberships
    assert state.writes == writes_after_first


def test_suspended_membership_is_stored_but_has_no_operational_context() -> None:
    state = MemoryState()
    subject = uuid4()
    account_id = uuid4()
    membership_id = uuid4()
    state.profiles.add(subject)
    state.accounts.add(account_id)
    state.memberships[membership_id] = ResolvedMembership(
        membership_id=membership_id,
        account_id=account_id,
        user_id=subject,
        role="owner",
        status="suspended",
    )
    writes_before = state.writes
    use_case = BootstrapAccountUseCase(MemoryUnitOfWorkFactory(state))

    with pytest.raises(ActiveMembershipRequired):
        asyncio.run(use_case.execute(AuthenticatedIdentity(subject=subject)))

    assert state.memberships[membership_id].status == "suspended"
    assert state.writes == writes_before


def test_failure_rolls_back_profile_account_and_membership() -> None:
    state = MemoryState()
    subject = uuid4()
    use_case = BootstrapAccountUseCase(MemoryUnitOfWorkFactory(state, fail_membership_insert=True))

    with pytest.raises(RuntimeError, match="injected membership failure"):
        asyncio.run(use_case.execute(AuthenticatedIdentity(subject=subject)))

    assert state.profiles == set()
    assert state.accounts == set()
    assert state.memberships == {}
    assert state.writes == 0
