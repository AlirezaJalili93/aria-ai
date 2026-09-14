from __future__ import annotations

import asyncio
from typing import Protocol, cast

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)

from app.modules.context.application.file_upload_ports import ObjectStorageError, ObjectStoragePort

STORAGE_CONNECT_TIMEOUT_SECONDS = 5
STORAGE_READ_TIMEOUT_SECONDS = 30


class S3Client(Protocol):
    def put_object(self, **kwargs: object) -> object: ...

    def delete_object(self, **kwargs: object) -> object: ...


class SupabaseS3ObjectStorage(ObjectStoragePort):
    def __init__(
        self,
        *,
        endpoint_url: str,
        region_name: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        client: S3Client | None = None,
    ) -> None:
        self._bucket = bucket
        self._client = client or cast(
            S3Client,
            cast(
                BaseClient,
                boto3.client(
                    "s3",
                    endpoint_url=endpoint_url,
                    region_name=region_name,
                    aws_access_key_id=access_key_id,
                    aws_secret_access_key=secret_access_key,
                    config=Config(
                        signature_version="s3v4",
                        connect_timeout=STORAGE_CONNECT_TIMEOUT_SECONDS,
                        read_timeout=STORAGE_READ_TIMEOUT_SECONDS,
                        retries={"total_max_attempts": 1, "mode": "standard"},
                        s3={"addressing_style": "path"},
                    ),
                ),
            ),
        )

    async def put_private(self, *, object_key: str, content: bytes, mime_type: str) -> None:
        try:
            await asyncio.to_thread(
                self._client.put_object,
                Bucket=self._bucket,
                Key=object_key,
                Body=content,
                ContentType=mime_type,
            )
        except _UNKNOWN_PUT_OUTCOME_ERRORS:
            raise ObjectStorageError(
                retryable=False,
                reason_code="provider_put_outcome_unknown",
                outcome_unknown=True,
            ) from None
        except _CONNECTION_ERRORS:
            raise ObjectStorageError(
                retryable=True,
                reason_code="provider_network_transient",
            ) from None
        except ClientError as error:
            raise _mapped_client_error(error) from None
        except BotoCoreError:
            raise ObjectStorageError(
                retryable=False,
                reason_code="provider_protocol_or_configuration",
            ) from None

    async def delete(self, *, object_key: str) -> None:
        try:
            await asyncio.to_thread(
                self._client.delete_object,
                Bucket=self._bucket,
                Key=object_key,
            )
        except _TRANSIENT_ERRORS:
            raise ObjectStorageError(
                retryable=True,
                reason_code="compensation_network_transient",
            ) from None
        except ClientError as error:
            status_code = _http_status(error)
            if status_code == 404:
                return
            raise _mapped_client_error(error, compensation=True) from None
        except BotoCoreError:
            raise ObjectStorageError(
                retryable=False,
                reason_code="compensation_protocol_or_configuration",
            ) from None


_UNKNOWN_PUT_OUTCOME_ERRORS = (
    ReadTimeoutError,
    ConnectionClosedError,
)

_CONNECTION_ERRORS = (ConnectTimeoutError, EndpointConnectionError)

_TRANSIENT_ERRORS = _UNKNOWN_PUT_OUTCOME_ERRORS + _CONNECTION_ERRORS


def _mapped_client_error(
    error: ClientError,
    *,
    compensation: bool = False,
) -> ObjectStorageError:
    status_code = _http_status(error)
    retryable = status_code == 429 or status_code >= 500
    if retryable:
        reason = "provider_response_transient"
    elif status_code in {401, 403}:
        reason = "provider_auth_or_configuration"
    elif status_code == 409:
        reason = "object_already_exists"
    else:
        reason = "provider_request_rejected"
    if compensation:
        reason = f"compensation_{reason}"
    return ObjectStorageError(retryable=retryable, reason_code=reason)


def _http_status(error: ClientError) -> int:
    response_metadata = error.response.get("ResponseMetadata", {})
    value = response_metadata.get("HTTPStatusCode", 0)
    return value if isinstance(value, int) else 0
