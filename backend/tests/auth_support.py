"""Shared ES256/JWKS test helpers. No real secrets or network access."""

from __future__ import annotations

import time
import uuid
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.auth.jwt import SupabaseTokenVerifier
from app.core.config import Settings

AUDIENCE = "authenticated"
PROJECT_URL = "https://project.supabase.co"
ISSUER = f"{PROJECT_URL}/auth/v1"
TOKEN_KID = "test-es256-kid"


def public_pem(private_key: Any) -> str:
    return (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )


def generate_ec_key() -> Any:
    return ec.generate_private_key(ec.SECP256R1())


PRIVATE_KEY = generate_ec_key()
PUBLIC_KEY_PEM = public_pem(PRIVATE_KEY)


class SigningKey:
    def __init__(self, key: str) -> None:
        self.key = key


class FakeJWKSClient:
    """Deterministic stand-in for PyJWKClient's cached key lookup."""

    def __init__(self, keys: dict[str, str]) -> None:
        self._keys = keys

    def get_signing_key_from_jwt(self, token: str) -> SigningKey:
        header = jwt.get_unverified_header(token)
        return SigningKey(self._keys[header["kid"]])


def make_settings(**overrides: Any) -> Settings:
    values = {
        "_env_file": None,
        "app_env": "testing",
        "supabase_url": PROJECT_URL,
        "supabase_jwt_audience": AUDIENCE,
    }
    values.update(overrides)
    return Settings(**values)


def make_claims(**overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    claims = {
        "sub": str(uuid.uuid4()),
        "email": "citizen@example.com",
        "role": "authenticated",
        "aud": AUDIENCE,
        "iss": ISSUER,
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(overrides)
    if "sub" in claims:
        claims["sub"] = str(claims["sub"])
    return claims


def make_token(
    private_key: Any = PRIVATE_KEY,
    *,
    kid: str = TOKEN_KID,
    algorithm: str = "ES256",
    **overrides: Any,
) -> str:
    return jwt.encode(
        make_claims(**overrides),
        private_key,
        algorithm=algorithm,
        headers={"kid": kid},
    )


def make_verifier(
    settings: Settings | None = None,
    *,
    keys: dict[str, str] | None = None,
) -> SupabaseTokenVerifier:
    if keys is None:
        keys = {TOKEN_KID: PUBLIC_KEY_PEM}
    return SupabaseTokenVerifier(
        settings or make_settings(),
        jwks_client=FakeJWKSClient(keys),
    )
