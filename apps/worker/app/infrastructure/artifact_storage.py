from __future__ import annotations

import asyncio
from typing import Protocol, cast

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.application.artifact_generation_runtime import (
    ArtifactGenerationError,
    StoredObject,
    digest,
)


class ArtifactS3Client(Protocol):
    def get_object(self, **kwargs: object) -> dict[str, object]: ...

    def put_object(self, **kwargs: object) -> object: ...


class S3PrivateArtifactStorage:
    def __init__(
        self,
        *,
        endpoint_url: str,
        region_name: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        client: ArtifactS3Client | None = None,
    ) -> None:
        self._bucket = bucket
        self._client = client or cast(
            ArtifactS3Client,
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
                        connect_timeout=5,
                        read_timeout=30,
                        retries={"total_max_attempts": 1, "mode": "standard"},
                        s3={"addressing_style": "path"},
                    ),
                ),
            ),
        )

    async def read(self, key: str) -> bytes | None:
        try:
            response = await asyncio.to_thread(
                self._client.get_object, Bucket=self._bucket, Key=key
            )
            body = response.get("Body")
            if body is None or not hasattr(body, "read"):
                raise ArtifactGenerationError("ARTIFACT_STORAGE_ERROR", retryable=True)
            try:
                return cast(bytes, await asyncio.to_thread(body.read))
            finally:
                if hasattr(body, "close"):
                    await asyncio.to_thread(body.close)
        except ClientError as error:
            status = int(error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
            if status == 404:
                return None
            raise ArtifactGenerationError("ARTIFACT_STORAGE_ERROR", retryable=True) from None
        except BotoCoreError:
            raise ArtifactGenerationError("ARTIFACT_STORAGE_ERROR", retryable=True) from None

    async def create_or_verify(self, key: str, content: bytes) -> StoredObject:
        expected = digest(content)
        existing = await self.read(key)
        if existing is not None:
            if digest(existing) != expected:
                raise ArtifactGenerationError("ARTIFACT_STORAGE_CONFLICT")
            return StoredObject(key=key, sha256=expected)
        try:
            await asyncio.to_thread(
                self._client.put_object,
                Bucket=self._bucket,
                Key=key,
                Body=content,
                ContentType="application/octet-stream",
                IfNoneMatch="*",
            )
        except ClientError as error:
            status = int(error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
            if status in {409, 412}:
                winner = await self.read(key)
                if winner is not None and digest(winner) == expected:
                    return StoredObject(key=key, sha256=expected)
                raise ArtifactGenerationError("ARTIFACT_STORAGE_CONFLICT") from None
            raise ArtifactGenerationError("ARTIFACT_STORAGE_ERROR", retryable=True) from None
        except BotoCoreError:
            raise ArtifactGenerationError("ARTIFACT_STORAGE_ERROR", retryable=True) from None
        read_back = await self.read(key)
        if read_back is None or digest(read_back) != expected:
            raise ArtifactGenerationError("ARTIFACT_STORAGE_ERROR", retryable=True)
        return StoredObject(key=key, sha256=expected)
