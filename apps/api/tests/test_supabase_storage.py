from __future__ import annotations

import asyncio

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ClientError, ConnectTimeoutError, ReadTimeoutError

from app.modules.context.application.file_upload_ports import ObjectStorageError
from app.modules.context.infrastructure.supabase_storage import SupabaseS3ObjectStorage


class FakeS3Client:
    def __init__(self) -> None:
        self.put_calls: list[dict[str, object]] = []
        self.delete_calls: list[dict[str, object]] = []
        self.put_error: Exception | None = None
        self.delete_error: Exception | None = None

    def put_object(self, **kwargs: object) -> object:
        self.put_calls.append(kwargs)
        if self.put_error is not None:
            raise self.put_error
        return {}

    def delete_object(self, **kwargs: object) -> object:
        self.delete_calls.append(kwargs)
        if self.delete_error is not None:
            raise self.delete_error
        return {}


def _storage(client: FakeS3Client) -> SupabaseS3ObjectStorage:
    return SupabaseS3ObjectStorage(
        endpoint_url="https://project.storage.supabase.co/storage/v1/s3",
        region_name="eu-central-1",
        bucket="private-context",
        access_key_id="test-access",
        secret_access_key="test-secret",
        client=client,
    )


def test_adapter_uploads_private_content_without_public_url_acl_or_upsert_options() -> None:
    client = FakeS3Client()
    asyncio.run(
        _storage(client).put_private(
            object_key="test/account/project/source/version",
            content=b"safe",
            mime_type="text/plain",
        )
    )
    assert client.put_calls == [
        {
            "Bucket": "private-context",
            "Key": "test/account/project/source/version",
            "Body": b"safe",
            "ContentType": "text/plain",
        }
    ]
    assert not ({"ACL", "x-upsert", "Upsert"} & set(client.put_calls[0]))


def test_adapter_builds_sigv4_path_client_with_frozen_timeouts_and_no_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    client = FakeS3Client()

    def fake_client(service: str, **kwargs: object) -> FakeS3Client:
        captured["service"] = service
        captured.update(kwargs)
        return client

    monkeypatch.setattr(boto3, "client", fake_client)
    _storage_without_client()

    assert captured["service"] == "s3"
    assert captured["endpoint_url"] == "https://project.storage.supabase.co/storage/v1/s3"
    assert captured["region_name"] == "eu-central-1"
    config = captured["config"]
    assert isinstance(config, Config)
    assert config.signature_version == "s3v4"
    assert config.connect_timeout == 5
    assert config.read_timeout == 30
    assert config.retries == {"total_max_attempts": 1, "mode": "standard"}
    assert config.s3 == {"addressing_style": "path"}


def test_adapter_classifies_network_and_configuration_failures_without_details() -> None:
    client = FakeS3Client()
    client.put_error = ConnectTimeoutError(endpoint_url="https://redacted.invalid")
    with pytest.raises(ObjectStorageError) as transient:
        asyncio.run(
            _storage(client).put_private(
                object_key="test/account/project/source/version",
                content=b"safe",
                mime_type="text/plain",
            )
        )
    assert transient.value.retryable is True
    assert transient.value.reason_code == "provider_network_transient"
    assert "redacted.invalid" not in str(transient.value)

    client.put_error = ClientError(
        {
            "Error": {"Code": "AccessDenied", "Message": "secret provider detail"},
            "ResponseMetadata": {"HTTPStatusCode": 403},
        },
        "PutObject",
    )
    with pytest.raises(ObjectStorageError) as configuration:
        asyncio.run(
            _storage(client).put_private(
                object_key="test/account/project/source/version",
                content=b"safe",
                mime_type="text/plain",
            )
        )
    assert configuration.value.retryable is False
    assert configuration.value.reason_code == "provider_auth_or_configuration"
    assert "secret provider detail" not in str(configuration.value)


def test_adapter_marks_read_timeout_as_unknown_put_outcome() -> None:
    client = FakeS3Client()
    client.put_error = ReadTimeoutError(endpoint_url="https://redacted.invalid")

    with pytest.raises(ObjectStorageError) as timeout:
        asyncio.run(
            _storage(client).put_private(
                object_key="test/account/project/source/version",
                content=b"safe",
                mime_type="text/plain",
            )
        )

    assert timeout.value.retryable is False
    assert timeout.value.outcome_unknown is True
    assert timeout.value.reason_code == "provider_put_outcome_unknown"
    assert "redacted.invalid" not in str(timeout.value)


def test_compensation_delete_treats_missing_object_as_success() -> None:
    client = FakeS3Client()
    client.delete_error = ClientError(
        {
            "Error": {"Code": "NoSuchKey", "Message": "not found"},
            "ResponseMetadata": {"HTTPStatusCode": 404},
        },
        "DeleteObject",
    )
    asyncio.run(_storage(client).delete(object_key="test/account/project/source/version"))
    assert len(client.delete_calls) == 1


def _storage_without_client() -> SupabaseS3ObjectStorage:
    return SupabaseS3ObjectStorage(
        endpoint_url="https://project.storage.supabase.co/storage/v1/s3",
        region_name="eu-central-1",
        bucket="private-context",
        access_key_id="test-access",
        secret_access_key="test-secret",
    )
