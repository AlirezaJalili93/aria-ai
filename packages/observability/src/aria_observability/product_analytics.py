from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID, uuid5

PRODUCT_ANALYTICS_CATEGORY = "product_analytics"
PRODUCT_ANALYTICS_SCHEMA_VERSION = "1"
PRODUCT_EVENT_NAMES = frozenset(
    {
        "project_created",
        "context_added",
        "structuring_started",
        "structuring_completed",
        "requirements_generated",
        "gap_detected",
        "gap_resolved",
        "scope_generated",
        "scope_version_saved",
    }
)
SOURCE_SURFACES = frozenset(
    {"project_overview", "context_page", "requirements_page", "gaps_page", "scope_page", "system"}
)
PROJECT_TYPES = frozenset({"landing", "corporate", "portfolio"})
ROLES = frozenset({"owner", "admin", "member"})
_EVENT_PROPERTIES: dict[str, frozenset[str]] = {
    "project_created": frozenset({"project_type", "role", "source_surface"}),
    "context_added": frozenset({"source_id", "context_version", "source_surface"}),
    "structuring_started": frozenset({"context_version"}),
    "structuring_completed": frozenset({"context_version"}),
    "requirements_generated": frozenset({"context_version"}),
    "gap_detected": frozenset({"gap_id", "context_version"}),
    "gap_resolved": frozenset({"gap_id", "context_version"}),
    "scope_generated": frozenset({"context_version"}),
    "scope_version_saved": frozenset({"context_version", "version_no"}),
}


class ProductAnalyticsContractError(ValueError):
    """A product analytics event violates the frozen L01 contract."""


@dataclass(frozen=True, slots=True)
class ProductAnalyticsEvent:
    event_id: UUID
    event_name: str
    account_id: UUID
    project_id: UUID
    actor_id: UUID | None
    properties: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, UUID) or not isinstance(self.account_id, UUID):
            raise ProductAnalyticsContractError("event_id and account_id must be UUIDs")
        if not isinstance(self.project_id, UUID):
            raise ProductAnalyticsContractError("project_id must be a UUID")
        if self.actor_id is not None and not isinstance(self.actor_id, UUID):
            raise ProductAnalyticsContractError("actor_id must be a UUID")
        if self.event_name not in PRODUCT_EVENT_NAMES:
            raise ProductAnalyticsContractError("Unknown product analytics event")
        allowed = _EVENT_PROPERTIES[self.event_name]
        if set(self.properties) - allowed:
            raise ProductAnalyticsContractError("Unknown product analytics property")
        for key, value in self.properties.items():
            if key.endswith("_id"):
                try:
                    UUID(str(value))
                except (TypeError, ValueError) as exc:
                    raise ProductAnalyticsContractError(f"{key} must be a UUID") from exc
            elif key == "context_version" or key == "version_no":
                if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                    raise ProductAnalyticsContractError(f"{key} must be a positive integer")
            elif key == "source_surface" and value not in SOURCE_SURFACES:
                raise ProductAnalyticsContractError("source_surface is not allowed")
            elif key == "project_type" and value not in PROJECT_TYPES:
                raise ProductAnalyticsContractError("project_type is not allowed")
            elif key == "role" and value not in ROLES:
                raise ProductAnalyticsContractError("role is not allowed")
            elif not isinstance(value, str) or not value:
                raise ProductAnalyticsContractError(f"{key} must be a safe enum value")


def stable_product_event_id(event_name: str, logical_id: UUID) -> UUID:
    if event_name not in PRODUCT_EVENT_NAMES:
        raise ProductAnalyticsContractError("Unknown product analytics event")
    if not isinstance(logical_id, UUID):
        raise ProductAnalyticsContractError("logical_id must be a UUID")
    return uuid5(UUID("6f0d8a2d-bc18-4f90-a4e8-1b26bb77b6b1"), f"{event_name}:{logical_id}")


def emit_product_analytics(
    logger: object,
    *,
    event_name: str,
    logical_id: UUID,
    account_id: UUID,
    project_id: UUID,
    actor_id: UUID | None = None,
    properties: Mapping[str, object] | None = None,
) -> None:
    emitter = getattr(logger, "emit_product_analytics", None)
    event = ProductAnalyticsEvent(
        event_id=stable_product_event_id(event_name, logical_id),
        event_name=event_name,
        account_id=account_id,
        project_id=project_id,
        actor_id=actor_id,
        properties=properties or {},
    )
    if callable(emitter):
        emitter(event)
        return

    # Keep the port usable by lightweight adapters while the canonical logger
    # remains responsible for the exact JSON envelope and durable deduplication.
    generic_emitter = getattr(logger, "emit", None)
    if callable(generic_emitter):
        generic_emitter(
            event.event_name,
            event_id=str(event.event_id),
            event_category=PRODUCT_ANALYTICS_CATEGORY,
            schema_version=PRODUCT_ANALYTICS_SCHEMA_VERSION,
            account_id=str(event.account_id),
            project_id=str(event.project_id),
            actor_id=str(event.actor_id) if event.actor_id else None,
            properties=dict(event.properties),
        )
        return
    raise ProductAnalyticsContractError("Analytics logger does not support product events")
