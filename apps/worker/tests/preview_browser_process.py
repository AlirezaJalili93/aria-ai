"""Captured-pipe Browser proof IPC; no token/config in arguments, files or logs."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from uuid import UUID

import pytest

ROOT = Path(__file__).parents[3]
CHECKS = (
    "pages_pass",
    "navigation",
    "isolation",
    "sandbox",
    "parent_stayed",
    "unauthorized_embed",
    "headers",
    "zero_fonts",
    "zero_unexpected_network",
    "zero_core_effects",
    "zero_downloads",
)


class BrowserProof:
    def __init__(self, process, core_port, page_count):
        self.process = process
        self.core_port = core_port
        self.page_count = page_count

    @classmethod
    async def start(cls, version: UUID, pages: list[str], profile_parent: Path):
        environment = {
            k: v
            for k, v in os.environ.items()
            if k.upper()
            in {
                "PATH",
                "SYSTEMROOT",
                "APPDATA",
                "LOCALAPPDATA",
                "USERPROFILE",
                "TMP",
                "TEMP",
            }
        }
        process = await asyncio.create_subprocess_exec(
            "node",
            str(ROOT / "scripts/preview-publication/browser-proof.mjs"),
            cwd=ROOT,
            env=environment,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        proof = cls(process, None, len(pages))
        try:
            process.stdin.write(
                json.dumps(
                    {
                        "artifact_version_id": str(version),
                        "pages": pages,
                        "profile_parent": str(profile_parent),
                    }
                ).encode()
                + b"\n"
            )
            await process.stdin.drain()
            value = json.loads(await process.stdout.readline())
            if set(value) != {"core_port"} or not str(value["core_port"]).isdigit():
                pytest.fail("Browser setup rejected (diagnostics withheld)")
            proof.core_port = int(value["core_port"])
            if not 1 <= proof.core_port <= 65535:
                pytest.fail("Browser setup port invalid")
            return proof
        except BaseException:
            await proof.close()
            raise

    async def execute(self, port: int, token: str, project_type: str):
        self.process.stdin.write(
            json.dumps({"preview_port": port, "token": token}).encode() + b"\n"
        )
        await self.process.stdin.drain()
        value = json.loads(await self.process.stdout.readline())
        if token in json.dumps(value):
            pytest.fail("Capability in Browser evidence (value withheld)")
        failed = [name for name in CHECKS if value.get(name) is not True]
        if value.get("status") != "PASS" or failed or value.get("pages") != self.page_count:
            stage = value.get("stage")
            if stage not in {
                "startup",
                "pages",
                "iframe_attach",
                "page_ready",
                "page_resources",
                "navigation",
                "isolation",
                "unauthorized_embed",
                "setup_or_cleanup",
            }:
                stage = "acceptance"
            labels = value.get("page_failures", [])
            allowed = {
                "loaded",
                "one_main",
                "one_h1",
                "rtl",
                "css",
                "images",
                "references",
                "script_free",
            }
            labels = [label for label in labels if isinstance(label, str) and label in allowed]
            classes = value.get("unexpected_classes", {})
            counts = ",".join(
                f"{label}={classes[label]}"
                for label in ("synthetic_data_probe", "external_network", "other")
                if isinstance(classes, dict)
                and type(classes.get(label)) is int
                and 0 <= classes[label] <= 10000
            )
            pytest.fail(
                f"Browser gate failed: stage={stage}; checks={','.join(failed)}; "
                f"page_checks={','.join(labels)}; request_classes={counts}"
            )
        if project_type == "landing" and value.get("form_seen") is not True:
            pytest.fail("Real SimpleForm proof missing")
        await self.close()

    async def close(self):
        if self.process.stdin and not self.process.stdin.is_closing():
            self.process.stdin.close()
        await self.process.wait()
        diagnostic = await self.process.stderr.read()
        if diagnostic or self.process.returncode != 0:
            pytest.fail("Browser process/cleanup failed (diagnostics withheld)")
