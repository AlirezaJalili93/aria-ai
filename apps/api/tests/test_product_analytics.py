from __future__ import annotations

import json
from io import StringIO
from uuid import UUID, uuid4

import pytest
from aria_observability import (
    ProductAnalyticsContractError,
    ProductAnalyticsEvent,
    create_event_logger,
    emit_product_analytics,
    stable_product_event_id,
)


def _logger(stream: StringIO):
    return create_event_logger(
        service="aria-api",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )


def test_product_event_emits_versioned_safe_envelope_and_deduplicates() -> None:
    stream = StringIO()
    account_id, project_id = uuid4(), uuid4()
    event_id = stable_product_event_id("project_created", project_id)
    logger = _logger(stream)

    emit_product_analytics(
        logger,
        event_name="project_created",
        logical_id=project_id,
        account_id=account_id,
        project_id=project_id,
        actor_id=account_id,
        properties={
            "project_type": "landing",
            "role": "owner",
            "source_surface": "system",
        },
    )
    emit_product_analytics(
        logger,
        event_name="project_created",
        logical_id=project_id,
        account_id=account_id,
        project_id=project_id,
        actor_id=account_id,
        properties={
            "project_type": "landing",
            "role": "owner",
            "source_surface": "system",
        },
    )

    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert len(events) == 1
    event = events[0]
    assert event["event_id"] == str(event_id)
    assert event["event_category"] == "product_analytics"
    assert event["schema_version"] == "1"
    assert event["account_id"] == str(account_id)
    assert event["project_id"] == str(project_id)
    assert event["actor_id"] == str(account_id)
    assert event["properties"] == {
        "project_type": "landing",
        "role": "owner",
        "source_surface": "system",
    }


@pytest.mark.parametrize(
    ("event_name", "properties"),
    [
        ("project_created", {"title": "must-not-log"}),
        ("gap_detected", {"gap_id": "not-a-uuid", "context_version": 1}),
        ("scope_version_saved", {"version_no": 0}),
        ("project_created", {"project_type": "unknown", "role": "owner"}),
    ],
)
def test_product_event_rejects_contract_violations(
    event_name: str, properties: dict[str, object]
) -> None:
    with pytest.raises(ProductAnalyticsContractError):
        ProductAnalyticsEvent(
            event_id=uuid4(),
            event_name=event_name,
            account_id=uuid4(),
            project_id=uuid4(),
            actor_id=None,
            properties=properties,
        )


def test_stable_event_ids_are_uuid5_and_event_specific() -> None:
    logical_id = uuid4()
    first = stable_product_event_id("gap_detected", logical_id)
    second = stable_product_event_id("gap_detected", logical_id)
    different_event = stable_product_event_id("gap_resolved", logical_id)

    assert isinstance(first, UUID)
    assert first == second
    assert first != different_event


def test_product_event_rejects_non_uuid_envelope_values() -> None:
    with pytest.raises(ProductAnalyticsContractError):
        ProductAnalyticsEvent(
            event_id="not-a-uuid",  # type: ignore[arg-type]
            event_name="project_created",
            account_id=uuid4(),
            project_id=uuid4(),
            actor_id=None,
            properties={},
        )
