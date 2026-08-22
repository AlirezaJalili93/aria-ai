from pathlib import Path

CONTRACT_PATH = Path("packages/contracts/openapi.yaml")


def test_openapi_documents_operational_health_contract() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "  - url: /api/v1" in contract
    assert "  /health/live:" in contract
    assert "  /health/ready:" in contract
    assert '"200":' in contract
    assert '"503":' in contract
    assert "release_commit_sha:" in contract
    assert 'pattern: "^[0-9a-fA-F]{40}$"' in contract
    assert "required: [configuration, database, queue]" in contract
    assert "AI providers are deliberately excluded" in contract
