from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from io import BytesIO

import pytest
from botocore.exceptions import ClientError, ReadTimeoutError

from app.application.txt_parser_consumer import TXT_MAX_BYTES, StoredObjectReadError
from app.infrastructure.storage.supabase_s3 import SupabaseS3PrivateObjectReader


class _Body(BytesIO):
    closed_by_reader = False

    def close(self) -> None:
        self.closed_by_reader = True
        super().close()


@dataclass
class _Client:
    body: bytes = b"valid"
    error: Exception | None = None
    calls: list[dict[str, object]] = field(default_factory=list)
    stream: _Body | None = None

    def get_object(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        self.stream = _Body(self.body)
        return {"Body": self.stream}


def _reader(client: _Client) -> SupabaseS3PrivateObjectReader:
    return SupabaseS3PrivateObjectReader(
        endpoint_url="https://storage.example.test/storage/v1/s3",
        region_name="eu-central-1",
        bucket="private-context",
        access_key_id="test-access",
        secret_access_key="test-secret",
        client=client,
    )


def test_reader_gets_one_private_key_and_closes_the_bounded_stream() -> None:
    client = _Client(body="متن".encode())

    content = asyncio.run(
        _reader(client).read_private(storage_reference="account/project/version.txt")
    )

    assert content == "متن".encode()
    assert client.calls == [
        {"Bucket": "private-context", "Key": "account/project/version.txt"}
    ]
    assert client.stream is not None and client.stream.closed_by_reader is True


def test_reader_rejects_stored_object_over_the_frozen_byte_limit() -> None:
    client = _Client(body=b"a" * (TXT_MAX_BYTES + 1))

    with pytest.raises(StoredObjectReadError) as raised:
        asyncio.run(_reader(client).read_private(storage_reference="version.txt"))

    assert raised.value.retryable is False
    assert raised.value.reason_code == "stored_object_too_large"
    assert client.stream is not None and client.stream.closed_by_reader is True


@pytest.mark.parametrize(
    ("error", "retryable", "reason_code"),
    [
        (
            ReadTimeoutError(endpoint_url="https://storage.example.test"),
            True,
            "provider_network_transient",
        ),
        (
            ClientError(
                {
                    "Error": {"Code": "SlowDown", "Message": "provider detail"},
                    "ResponseMetadata": {"HTTPStatusCode": 503},
                },
                "GetObject",
            ),
            True,
            "provider_response_transient",
        ),
        (
            ClientError(
                {
                    "Error": {"Code": "AccessDenied", "Message": "provider detail"},
                    "ResponseMetadata": {"HTTPStatusCode": 403},
                },
                "GetObject",
            ),
            False,
            "provider_request_rejected",
        ),
    ],
)
def test_reader_maps_provider_failures_to_bounded_safe_errors(
    error: Exception,
    retryable: bool,
    reason_code: str,
) -> None:
    with pytest.raises(StoredObjectReadError) as raised:
        asyncio.run(
            _reader(_Client(error=error)).read_private(storage_reference="version.txt")
        )

    assert raised.value.retryable is retryable
    assert raised.value.reason_code == reason_code
    assert "provider detail" not in str(raised.value)
