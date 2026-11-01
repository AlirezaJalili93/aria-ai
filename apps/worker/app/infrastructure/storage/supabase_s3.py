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

from app.application.txt_parser_consumer import TXT_MAX_BYTES, StoredObjectReadError

STORAGE_CONNECT_TIMEOUT_SECONDS = 5
STORAGE_READ_TIMEOUT_SECONDS = 30


class StreamingBody(Protocol):
    def read(self, amount: int | None = None) -> bytes: ...

    def close(self) -> None: ...


class S3ReadClient(Protocol):
    def get_object(self, **kwargs: object) -> dict[str, object]: ...


class SupabaseS3PrivateObjectReader:
    def __init__(
        self,
        *,
        endpoint_url: str,
        region_name: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        client: S3ReadClient | None = None,
    ) -> None:
        self._bucket = bucket
        self._client = client or cast(
            S3ReadClient,
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

    async def read_private(self, *, storage_reference: str) -> bytes:
        try:
            response = await asyncio.to_thread(
                self._client.get_object,
                Bucket=self._bucket,
                Key=storage_reference,
            )
            return await asyncio.to_thread(_read_bounded_body, response)
        except (
            ReadTimeoutError,
            ConnectionClosedError,
            ConnectTimeoutError,
            EndpointConnectionError,
        ):
            raise StoredObjectReadError(
                retryable=True,
                reason_code="provider_network_transient",
            ) from None
        except ClientError as error:
            status_code = _http_status(error)
            raise StoredObjectReadError(
                retryable=status_code == 429 or status_code >= 500,
                reason_code=(
                    "provider_response_transient"
                    if status_code == 429 or status_code >= 500
                    else "provider_request_rejected"
                ),
            ) from None
        except BotoCoreError:
            raise StoredObjectReadError(
                retryable=False,
                reason_code="provider_protocol_or_configuration",
            ) from None


def _read_bounded_body(response: dict[str, object]) -> bytes:
    body = response.get("Body")
    if body is None or not hasattr(body, "read") or not hasattr(body, "close"):
        raise StoredObjectReadError(
            retryable=False,
            reason_code="provider_invalid_response",
        )
    stream = cast(StreamingBody, body)
    try:
        content = stream.read(TXT_MAX_BYTES + 1)
    finally:
        stream.close()
    if len(content) > TXT_MAX_BYTES:
        raise StoredObjectReadError(
            retryable=False,
            reason_code="stored_object_too_large",
        )
    return content


def _http_status(error: ClientError) -> int:
    metadata = error.response.get("ResponseMetadata", {})
    value = metadata.get("HTTPStatusCode", 0)
    return value if isinstance(value, int) else 0
