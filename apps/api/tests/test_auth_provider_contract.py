from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from threading import Thread
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import jwt
import pytest
from aria_observability import (
    bind_trace_context,
    create_event_logger,
    resolve_http_trace_context,
)
from cryptography.hazmat.primitives.asymmetric.ec import (
    SECP256R1,
    EllipticCurvePrivateKey,
    generate_private_key,
)
from jwt.algorithms import ECAlgorithm

from app.infrastructure.auth.supabase_jwt import SupabaseJwtVerifier
from app.modules.identity.application.ports import (
    AuthProviderUnavailable,
    InvalidAccessToken,
)

ISSUER = "https://auth-contract.example.test/auth/v1"
AUDIENCE = "authenticated"


def _public_jwk(private_key: EllipticCurvePrivateKey, kid: str) -> dict[str, object]:
    value = ECAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    assert isinstance(value, dict)
    return {
        **value,
        "alg": "ES256",
        "kid": kid,
        "use": "sig",
        "key_ops": ["verify"],
    }


def _token(
    private_key: EllipticCurvePrivateKey,
    kid: str | None,
    *,
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    expires_at: datetime | None = None,
    subject: object | None = None,
) -> str:
    now = datetime.now(UTC)
    headers: dict[str, str] = {}
    if kid is not None:
        headers["kid"] = kid
    payload: dict[str, object] = {
        "iss": issuer,
        "aud": audience,
        "exp": expires_at or now + timedelta(minutes=5),
        "iat": now,
    }
    if subject is not None:
        payload["sub"] = subject
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


@contextmanager
def _rotating_jwks_server(
    responses: list[dict[str, object] | bytes],
) -> Iterator[tuple[str, list[int]]]:
    request_count = [0]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
            response_index = min(request_count[0], len(responses) - 1)
            request_count[0] += 1
            response = responses[response_index]
            payload = response if isinstance(response, bytes) else json.dumps(response).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/auth/v1/.well-known/jwks.json", request_count
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _verify(verifier: SupabaseJwtVerifier, token: str):
    return asyncio.run(verifier.verify(token))


def _event_logger(stream: StringIO):
    return create_event_logger(
        service="aria-api",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )


def test_verifier_configures_explicit_five_second_jwks_timeout() -> None:
    with patch("app.infrastructure.auth.supabase_jwt.PyJWKClient") as client_type:
        SupabaseJwtVerifier(
            jwks_url="https://auth-contract.example.test/.well-known/jwks.json",
            issuer=ISSUER,
            audience=AUDIENCE,
            clock_skew_seconds=30,
        )

    client_type.assert_called_once_with(
        "https://auth-contract.example.test/.well-known/jwks.json",
        cache_jwk_set=True,
        lifespan=600,
        timeout=5,
    )


def test_verifier_accepts_valid_es256_token_and_returns_provider_neutral_identity() -> None:
    private_key = generate_private_key(SECP256R1())
    kid = str(uuid4())
    subject = uuid4()
    jwks = {"keys": [_public_jwk(private_key, kid)]}

    with _rotating_jwks_server([jwks]) as (jwks_url, _):
        verifier = SupabaseJwtVerifier(
            jwks_url=jwks_url,
            issuer=ISSUER,
            audience=AUDIENCE,
            clock_skew_seconds=30,
        )

        identity = _verify(verifier, _token(private_key, kid, subject=str(subject)))

    assert identity.subject == subject
    assert isinstance(identity.subject, UUID)


def test_unknown_kid_refreshes_jwks_and_verifies_rotated_key_without_restart() -> None:
    first_key = generate_private_key(SECP256R1())
    rotated_key = generate_private_key(SECP256R1())
    first_kid = str(uuid4())
    rotated_kid = str(uuid4())
    first_jwks = {"keys": [_public_jwk(first_key, first_kid)]}
    rotated_jwks = {
        "keys": [
            _public_jwk(first_key, first_kid),
            _public_jwk(rotated_key, rotated_kid),
        ]
    }

    stream = StringIO()
    with _rotating_jwks_server([first_jwks, rotated_jwks]) as (jwks_url, count):
        verifier = SupabaseJwtVerifier(
            jwks_url=jwks_url,
            issuer=ISSUER,
            audience=AUDIENCE,
            clock_skew_seconds=30,
            event_logger=_event_logger(stream),
        )
        _verify(verifier, _token(first_key, first_kid, subject=str(uuid4())))
        with bind_trace_context(
            resolve_http_trace_context(
                "c11a58e5-546f-46e0-a68f-167e61f44971",
                "06635353-20c7-4db4-a102-f790439f2ab4",
            )
        ):
            rotated_identity = _verify(
                verifier,
                _token(rotated_key, rotated_kid, subject=str(uuid4())),
            )

    assert isinstance(rotated_identity.subject, UUID)
    assert count[0] == 2
    refresh_event = json.loads(stream.getvalue())
    assert refresh_event["event_name"] == "auth.jwks_refreshed"
    assert refresh_event["provider"] == "supabase"
    assert refresh_event["reason_code"] == "unknown_kid"
    assert refresh_event["request_id"] == "c11a58e5-546f-46e0-a68f-167e61f44971"
    assert refresh_event["correlation_id"] == "06635353-20c7-4db4-a102-f790439f2ab4"
    assert refresh_event["duration_ms"] >= 0


def test_approved_clock_skew_accepts_token_within_thirty_second_window() -> None:
    private_key = generate_private_key(SECP256R1())
    kid = str(uuid4())
    jwks = {"keys": [_public_jwk(private_key, kid)]}

    with _rotating_jwks_server([jwks]) as (jwks_url, _):
        verifier = SupabaseJwtVerifier(
            jwks_url=jwks_url,
            issuer=ISSUER,
            audience=AUDIENCE,
            clock_skew_seconds=30,
        )

        identity = _verify(
            verifier,
            _token(
                private_key,
                kid,
                subject=str(uuid4()),
                expires_at=datetime.now(UTC) - timedelta(seconds=28),
            ),
        )

    assert isinstance(identity.subject, UUID)


def test_verifier_rejects_unapproved_clock_skew_configuration() -> None:
    with pytest.raises(ValueError, match="approved 30 seconds"):
        SupabaseJwtVerifier(
            jwks_url="https://auth-contract.example.test/.well-known/jwks.json",
            issuer=ISSUER,
            audience=AUDIENCE,
            clock_skew_seconds=31,
        )


def test_verifier_rejects_jwk_algorithm_mismatch() -> None:
    private_key = generate_private_key(SECP256R1())
    kid = str(uuid4())
    mismatched_jwk = _public_jwk(private_key, kid)
    mismatched_jwk["alg"] = "ES384"
    jwks = {"keys": [mismatched_jwk]}

    with _rotating_jwks_server([jwks]) as (jwks_url, _):
        verifier = SupabaseJwtVerifier(
            jwks_url=jwks_url,
            issuer=ISSUER,
            audience=AUDIENCE,
            clock_skew_seconds=30,
        )

        with pytest.raises(InvalidAccessToken) as failure:
            _verify(verifier, _token(private_key, kid, subject=str(uuid4())))

    assert failure.value.reason_code == "algorithm_mismatch"


@pytest.mark.parametrize(
    ("token_factory", "expected_reason"),
    [
        pytest.param(
            lambda key, kid: "malformed",
            "malformed_token",
            id="malformed",
        ),
        pytest.param(
            lambda key, kid: _token(
                key,
                kid,
                subject=str(uuid4()),
                expires_at=datetime.now(UTC) - timedelta(seconds=31),
            ),
            "expired_token",
            id="expired-beyond-clock-skew",
        ),
        pytest.param(
            lambda key, kid: _token(
                key,
                kid,
                subject=str(uuid4()),
                audience="wrong-audience",
            ),
            "audience_mismatch",
            id="wrong-audience",
        ),
        pytest.param(
            lambda key, kid: _token(
                key,
                kid,
                subject=str(uuid4()),
                issuer="https://wrong-issuer.example.test/auth/v1",
            ),
            "issuer_mismatch",
            id="wrong-issuer",
        ),
        pytest.param(
            lambda key, kid: _token(key, kid),
            "missing_claim",
            id="missing-subject",
        ),
        pytest.param(
            lambda key, kid: _token(key, kid, subject="not-a-uuid"),
            "invalid_subject",
            id="invalid-subject",
        ),
        pytest.param(
            lambda key, kid: _token(key, kid, subject=1234),
            "invalid_subject",
            id="non-string-subject",
        ),
        pytest.param(
            lambda key, kid: _token(key, None, subject=str(uuid4())),
            "missing_kid",
            id="missing-kid",
        ),
        pytest.param(
            lambda key, kid: _token(key, str(uuid4()), subject=str(uuid4())),
            "unknown_kid",
            id="unknown-kid",
        ),
        pytest.param(
            lambda key, kid: jwt.encode(
                {
                    "iss": ISSUER,
                    "aud": AUDIENCE,
                    "exp": datetime.now(UTC) + timedelta(minutes=5),
                    "sub": str(uuid4()),
                },
                "contract-test-secret-that-is-long-enough",
                algorithm="HS256",
                headers={"kid": kid},
            ),
            "algorithm_mismatch",
            id="wrong-algorithm",
        ),
    ],
)
def test_verifier_rejects_invalid_tokens(
    token_factory: Any,
    expected_reason: str,
) -> None:
    private_key = generate_private_key(SECP256R1())
    kid = str(uuid4())
    jwks = {"keys": [_public_jwk(private_key, kid)]}

    with _rotating_jwks_server([jwks]) as (jwks_url, _):
        verifier = SupabaseJwtVerifier(
            jwks_url=jwks_url,
            issuer=ISSUER,
            audience=AUDIENCE,
            clock_skew_seconds=30,
        )

        with pytest.raises(InvalidAccessToken) as failure:
            _verify(verifier, token_factory(private_key, kid))

    assert failure.value.reason_code == expected_reason


def test_verifier_rejects_token_with_invalid_signature() -> None:
    trusted_key = generate_private_key(SECP256R1())
    attacker_key = generate_private_key(SECP256R1())
    kid = str(uuid4())
    jwks = {"keys": [_public_jwk(trusted_key, kid)]}

    with _rotating_jwks_server([jwks]) as (jwks_url, _):
        verifier = SupabaseJwtVerifier(
            jwks_url=jwks_url,
            issuer=ISSUER,
            audience=AUDIENCE,
            clock_skew_seconds=30,
        )

        with pytest.raises(InvalidAccessToken) as failure:
            _verify(verifier, _token(attacker_key, kid, subject=str(uuid4())))

    assert failure.value.reason_code == "invalid_signature"


def test_jwks_connection_failure_is_provider_unavailable_not_invalid_token() -> None:
    private_key = generate_private_key(SECP256R1())
    verifier = SupabaseJwtVerifier(
        jwks_url="http://127.0.0.1:1/auth/v1/.well-known/jwks.json",
        issuer=ISSUER,
        audience=AUDIENCE,
        clock_skew_seconds=30,
    )

    with pytest.raises(AuthProviderUnavailable) as failure:
        _verify(verifier, _token(private_key, str(uuid4()), subject=str(uuid4())))

    assert failure.value.reason_code == "jwks_unavailable"


def test_malformed_jwks_is_provider_unavailable_not_invalid_token() -> None:
    private_key = generate_private_key(SECP256R1())
    kid = str(uuid4())

    with _rotating_jwks_server([b"not-json"]) as (jwks_url, _):
        verifier = SupabaseJwtVerifier(
            jwks_url=jwks_url,
            issuer=ISSUER,
            audience=AUDIENCE,
            clock_skew_seconds=30,
        )

        with pytest.raises(AuthProviderUnavailable) as failure:
            _verify(verifier, _token(private_key, kid, subject=str(uuid4())))

    assert failure.value.reason_code == "jwks_unavailable"
