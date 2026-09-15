from __future__ import annotations

import asyncio
import os
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4

import pytest

from app.modules.context.infrastructure.supabase_storage import SupabaseS3ObjectStorage

RUN_HOSTED_UPLOAD_SECURITY = os.environ.get("RUN_HOSTED_UPLOAD_SECURITY") == "1"
pytestmark = pytest.mark.skipif(
    not RUN_HOSTED_UPLOAD_SECURITY,
    reason="RUN_HOSTED_UPLOAD_SECURITY=1 is required for hosted Supabase evidence",
)


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.fail(f"{name} is required for hosted upload security evidence")
    return value


def test_private_bucket_accepts_server_upload_but_denies_anonymous_access() -> None:
    project_url = _required_environment("NEXT_PUBLIC_SUPABASE_URL").rstrip("/")
    endpoint = _required_environment("STORAGE_ENDPOINT")
    region = _required_environment("STORAGE_REGION")
    bucket = _required_environment("STORAGE_BUCKET")
    access_key = _required_environment("STORAGE_ACCESS_KEY")
    secret_key = _required_environment("STORAGE_SECRET_KEY")
    object_key = "/".join(
        (
            "security-evidence",
            str(uuid4()),
            str(uuid4()),
            str(uuid4()),
            str(uuid4()),
        )
    )
    sentinel = f"aria-private-storage-{uuid4()}".encode()
    storage = SupabaseS3ObjectStorage(
        endpoint_url=endpoint,
        region_name=region,
        bucket=bucket,
        access_key_id=access_key,
        secret_access_key=secret_key,
    )
    public_url = (
        f"{project_url}/storage/v1/object/public/{quote(bucket, safe='')}/"
        f"{quote(object_key, safe='/')}"
    )
    private_download_url = (
        f"{project_url}/storage/v1/object/{quote(bucket, safe='')}/"
        f"{quote(object_key, safe='/')}"
    )
    list_url = f"{project_url}/storage/v1/object/list/{quote(bucket, safe='')}"

    def assert_anonymous_request_denied(request: Request) -> None:
        try:
            with urlopen(request, timeout=10) as response:  # noqa: S310
                response.read(1)
                pytest.fail("Private storage operation succeeded anonymously")
        except HTTPError as error:
            assert error.code in {400, 401, 403, 404}

    async def scenario() -> None:
        await storage.put_private(
            object_key=object_key,
            content=sentinel,
            mime_type="text/plain",
        )
        try:
            assert_anonymous_request_denied(Request(public_url, method="GET"))
            assert_anonymous_request_denied(Request(private_download_url, method="GET"))
            assert_anonymous_request_denied(
                Request(
                    list_url,
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
            )
        finally:
            await storage.delete(object_key=object_key)

    asyncio.run(scenario())
