from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from app.modules.identity.application.bootstrap_ports import (
    AccountBootstrapUnitOfWorkFactory,
    ResolvedMembership,
)
from app.modules.identity.application.membership_resolution import (
    ActiveMembershipRequired,
    MembershipDenialReason,
)
from app.modules.identity.application.ports import AuthenticatedIdentity
from app.modules.identity.domain.membership import ACTIVE_MEMBERSHIP_STATUS


class AccountBootstrapInvariantError(Exception):
    """The persisted projection is incomplete despite transactional bootstrap."""


class AccountBootstrapInfrastructureError(Exception):
    """A declared persistence failure prevented Account Bootstrap."""


@dataclass(frozen=True, slots=True)
class AccountBootstrapContext:
    subject: UUID
    active_memberships: tuple[ResolvedMembership, ...]
    created: bool


class AccountBootstrapper(Protocol):
    async def execute(self, identity: AuthenticatedIdentity) -> AccountBootstrapContext: ...


class BootstrapAccountUseCase:
    def __init__(
        self,
        unit_of_work_factory: AccountBootstrapUnitOfWorkFactory,
        *,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._id_factory = id_factory

    async def execute(self, identity: AuthenticatedIdentity) -> AccountBootstrapContext:
        async with self._unit_of_work_factory() as unit_of_work:
            existing = await unit_of_work.repository.resolve_memberships(identity.subject)
            if existing:
                return _context_from_memberships(identity.subject, existing, created=False)

            profile_created = await unit_of_work.repository.create_profile_if_absent(
                identity.subject
            )
            if not profile_created:
                concurrently_created = await unit_of_work.repository.resolve_memberships(
                    identity.subject
                )
                if not concurrently_created:
                    raise AccountBootstrapInvariantError
                return _context_from_memberships(
                    identity.subject,
                    concurrently_created,
                    created=False,
                )

            account_id = self._id_factory()
            membership_id = self._id_factory()
            await unit_of_work.repository.add_account(account_id)
            await unit_of_work.repository.add_owner_membership(
                membership_id=membership_id,
                account_id=account_id,
                user_id=identity.subject,
            )
            await unit_of_work.commit()
            return AccountBootstrapContext(
                subject=identity.subject,
                active_memberships=(
                    ResolvedMembership(
                        membership_id=membership_id,
                        account_id=account_id,
                        user_id=identity.subject,
                        role="owner",
                        status="active",
                    ),
                ),
                created=True,
            )


def inactive_account_bootstrap_context(
    identity: AuthenticatedIdentity,
) -> AccountBootstrapContext:
    """Represent an existing identity whose Account authorization is deferred."""
    return AccountBootstrapContext(
        subject=identity.subject,
        active_memberships=(),
        created=False,
    )


def _context_from_memberships(
    subject: UUID,
    memberships: tuple[ResolvedMembership, ...],
    *,
    created: bool,
) -> AccountBootstrapContext:
    active = tuple(
        membership for membership in memberships if membership.status == ACTIVE_MEMBERSHIP_STATUS
    )
    if not active:
        reason_code: MembershipDenialReason = (
            "invited"
            if any(membership.status == "invited" for membership in memberships)
            else "suspended"
        )
        raise ActiveMembershipRequired(reason_code=reason_code)
    return AccountBootstrapContext(
        subject=subject,
        active_memberships=active,
        created=created,
    )
