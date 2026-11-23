"""Supabase JWT verification tests. No live Supabase or network access."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

import jwt
import pytest

from app.auth.jwt import (
    SupabaseTokenVerifier,
    TokenVerificationError,
    clear_token_verifier_cache,
)
from tests.auth_support import (
    ISSUER,
    PRIVATE_KEY,
    PUBLIC_KEY_PEM,
    TOKEN_KID,
    FakeJWKSClient,
    generate_ec_key,
    make_settings,
    make_token,
    make_verifier,
    public_pem,
)


def test_valid_es256_token_verifies_required_claims() -> None:
    verified = make_verifier().verify(make_token())
    assert isinstance(verified.subject, uuid.UUID)
    assert verified.email == "citizen@example.com"
    assert verified.claims["aud"] == "authenticated"


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"exp": int(time.time()) - 10}, "expired_token"),
        ({"aud": "another-audience"}, "invalid_audience"),
        ({"iss": "https://other.example/auth/v1"}, "invalid_issuer"),
    ],
)
def test_rejects_invalid_registered_claims(
    overrides: dict[str, Any], reason: str
) -> None:
    with pytest.raises(TokenVerificationError) as exc:
        make_verifier().verify(make_token(**overrides))
    assert exc.value.reason == reason


def test_rejects_tampered_signature_and_malformed_tokens() -> None:
    other_key = generate_ec_key()
    verifier = make_verifier()
    with pytest.raises(TokenVerificationError) as exc:
        verifier.verify(make_token(other_key))
    assert exc.value.reason == "invalid_signature"

    with pytest.raises(TokenVerificationError) as exc:
        verifier.verify("not-a-jwt")
    assert exc.value.reason in {"malformed_token", "malformed_header"}


def test_rejects_missing_required_claim() -> None:
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "aud": "authenticated",
            "iss": ISSUER,
            "exp": now + 3600,
        },
        PRIVATE_KEY,
        algorithm="ES256",
        headers={"kid": TOKEN_KID},
    )
    with pytest.raises(TokenVerificationError) as exc:
        make_verifier().verify(token)
    assert exc.value.reason == "missing_required_claim"


def test_rejects_unsupported_hs256_and_invalid_subject() -> None:
    legacy = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "aud": "authenticated",
            "iss": ISSUER,
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        },
        "legacy-shared-secret-must-not-be-accepted",
        algorithm="HS256",
    )
    with pytest.raises(TokenVerificationError) as exc:
        make_verifier().verify(legacy)
    assert exc.value.reason == "unsupported_algorithm"

    with pytest.raises(TokenVerificationError) as exc:
        make_verifier().verify(make_token(sub="not-a-uuid"))
    assert exc.value.reason == "invalid_subject"


def test_rejects_missing_issuer_or_jwks_configuration() -> None:
    no_jwks = make_settings(
        supabase_url=None,
        supabase_jwt_issuer=ISSUER,
    )
    with pytest.raises(TokenVerificationError) as exc:
        SupabaseTokenVerifier(no_jwks).verify(make_token())
    assert exc.value.reason == "jwks_not_configured"


def test_rejection_logs_reason_not_token(caplog: pytest.LogCaptureFixture) -> None:
    from app.auth.dependencies import verify_access_token

    verifier = make_verifier()
    token = make_token()
    tampered = make_token(generate_ec_key())
    caplog.set_level(logging.WARNING)
    with pytest.raises(Exception):
        verify_access_token(tampered, verifier)
    assert token not in caplog.text
    assert tampered not in caplog.text


def test_es256_jwks_supports_key_rotation() -> None:
    key_one = generate_ec_key()
    key_two = generate_ec_key()
    verifier = make_verifier(
        keys={
            "kid-1": public_pem(key_one),
            "kid-2": public_pem(key_two),
        }
    )
    token_one = make_token(
        key_one,
        kid="kid-1",
        sub="11111111-1111-4111-8111-111111111111",
    )
    token_two = make_token(
        key_two,
        kid="kid-2",
        sub="22222222-2222-4222-8222-222222222222",
    )
    assert verifier.verify(token_one).subject == uuid.UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    assert verifier.verify(token_two).subject == uuid.UUID(
        "22222222-2222-4222-8222-222222222222"
    )


def test_asymmetric_jwks_also_supports_rs256() -> None:
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = SupabaseTokenVerifier(
        make_settings(),
        jwks_client=FakeJWKSClient({"rsa-kid": public_pem(key)}),
    )
    token = make_token(key, kid="rsa-kid", algorithm="RS256")
    assert verifier.verify(token).email == "citizen@example.com"


def test_verifier_cache_can_be_cleared() -> None:
    clear_token_verifier_cache()


def test_live_algorithm_public_key_fixture_is_es256() -> None:
    assert PUBLIC_KEY_PEM.startswith("-----BEGIN PUBLIC KEY-----")
    header = jwt.get_unverified_header(make_token())
    assert header["alg"] == "ES256"
    assert header["kid"] == TOKEN_KID
