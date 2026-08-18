from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ec import (
    SECP256R1,
    EllipticCurvePrivateKey,
    generate_private_key,
)
from jwt.algorithms import ECAlgorithm

from app.infrastructure.auth.supabase_jwt import SupabaseJwtVerifier
from app.modules.identity.application.ports import InvalidAccessToken

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
    subject: str | None = None,
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
    responses: list[dict[str, object]],
) -> Iterator[tuple[str, list[int]]]:
    request_count = [0]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
            response_index = min(request_count[0], len(responses) - 1)
            request_count[0] += 1
            payload = json.dumps(responses[response_index]).encode()
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

    with _rotating_jwks_server([first_jwks, rotated_jwks]) as (jwks_url, count):
        verifier = SupabaseJwtVerifier(
            jwks_url=jwks_url,
            issuer=ISSUER,
            audience=AUDIENCE,
            clock_skew_seconds=30,
        )
        _verify(verifier, _token(first_key, first_kid, subject=str(uuid4())))
        rotated_identity = _verify(
            verifier,
            _token(rotated_key, rotated_kid, subject=str(uuid4())),
        )

    assert isinstance(rotated_identity.subject, UUID)
    assert count[0] == 2


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

        with pytest.raises(InvalidAccessToken):
            _verify(verifier, _token(private_key, kid, subject=str(uuid4())))


@pytest.mark.parametrize(
    "token_factory",
    [
        pytest.param(lambda key, kid: "malformed", id="malformed"),
        pytest.param(
            lambda key, kid: _token(
                key,
                kid,
                subject=str(uuid4()),
                expires_at=datetime.now(UTC) - timedelta(seconds=31),
            ),
            id="expired-beyond-clock-skew",
        ),
        pytest.param(
            lambda key, kid: _token(
                key,
                kid,
                subject=str(uuid4()),
                audience="wrong-audience",
            ),
            id="wrong-audience",
        ),
        pytest.param(
            lambda key, kid: _token(
                key,
                kid,
                subject=str(uuid4()),
                issuer="https://wrong-issuer.example.test/auth/v1",
            ),
            id="wrong-issuer",
        ),
        pytest.param(lambda key, kid: _token(key, kid), id="missing-subject"),
        pytest.param(
            lambda key, kid: _token(key, kid, subject="not-a-uuid"),
            id="invalid-subject",
        ),
        pytest.param(
            lambda key, kid: _token(key, None, subject=str(uuid4())),
            id="missing-kid",
        ),
        pytest.param(
            lambda key, kid: _token(key, str(uuid4()), subject=str(uuid4())),
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
            id="wrong-algorithm",
        ),
    ],
)
def test_verifier_rejects_invalid_tokens(token_factory: Any) -> None:
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

        with pytest.raises(InvalidAccessToken):
            _verify(verifier, token_factory(private_key, kid))


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

        with pytest.raises(InvalidAccessToken):
            _verify(verifier, _token(attacker_key, kid, subject=str(uuid4())))
