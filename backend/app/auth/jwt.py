"""Supabase JWT verification.

Supabase tokens are verified asymmetrically with the project JWKS endpoint
(RS256/ES256). The legacy symmetric HS256 path is intentionally not supported:
the configured project uses ES256, and accepting a legacy shared secret would
expand the accepted signing surface.

No token is decoded without signature verification. JWT contents and keys are
never logged.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
    MissingRequiredClaimError,
)

from app.core.config import Settings, get_settings

ASYMMETRIC_ALGORITHMS = frozenset({"RS256", "ES256"})
REQUIRED_CLAIMS = ("exp", "iat", "sub", "aud", "iss")


class TokenVerificationError(Exception):
    """Safe internal verification failure; never contains the raw token."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class VerifiedToken:
    subject: uuid.UUID
    email: str | None
    claims: dict[str, Any]


class SupabaseTokenVerifier:
    def __init__(
        self,
        settings: Settings,
        *,
        jwks_client: PyJWKClient | None = None,
    ) -> None:
        self.issuer = settings.supabase_issuer
        self.audience = settings.supabase_jwt_audience
        self._jwks_url = settings.supabase_jwks_url_value
        self._jwks_client = jwks_client
        if self._jwks_client is None and self._jwks_url:
            self._jwks_client = PyJWKClient(
                self._jwks_url,
                cache_keys=True,
                lifespan=settings.supabase_jwks_cache_seconds,
            )

    def verify(self, token: str) -> VerifiedToken:
        if not token or token.count(".") != 2:
            raise TokenVerificationError("malformed_token")
        if not self.issuer:
            raise TokenVerificationError("issuer_not_configured")

        try:
            header = jwt.get_unverified_header(token)
        except InvalidTokenError as exc:
            raise TokenVerificationError("malformed_header") from exc

        algorithm = header.get("alg")
        if not isinstance(algorithm, str):
            raise TokenVerificationError("missing_algorithm")

        try:
            if algorithm not in ASYMMETRIC_ALGORITHMS:
                raise TokenVerificationError("unsupported_algorithm")
            claims = self._verify_asymmetric(token, algorithm)
        except TokenVerificationError:
            raise
        except ExpiredSignatureError as exc:
            raise TokenVerificationError("expired_token") from exc
        except InvalidAudienceError as exc:
            raise TokenVerificationError("invalid_audience") from exc
        except InvalidIssuerError as exc:
            raise TokenVerificationError("invalid_issuer") from exc
        except InvalidSignatureError as exc:
            raise TokenVerificationError("invalid_signature") from exc
        except MissingRequiredClaimError as exc:
            raise TokenVerificationError("missing_required_claim") from exc
        except InvalidTokenError as exc:
            raise TokenVerificationError("invalid_token") from exc

        subject = claims.get("sub")
        try:
            subject_uuid = uuid.UUID(str(subject))
        except (ValueError, TypeError, AttributeError) as exc:
            raise TokenVerificationError("invalid_subject") from exc

        email = claims.get("email")
        if email is not None and not isinstance(email, str):
            raise TokenVerificationError("invalid_email_claim")

        return VerifiedToken(
            subject=subject_uuid,
            email=email,
            claims=dict(claims),
        )

    def _decode_options(self) -> dict[str, Any]:
        return {
            "require": list(REQUIRED_CLAIMS),
            "verify_signature": True,
            "verify_exp": True,
            "verify_iat": True,
            "verify_nbf": True,
            "verify_aud": True,
            "verify_iss": True,
        }

    def _verify_asymmetric(self, token: str, algorithm: str) -> dict[str, Any]:
        if self._jwks_client is None:
            raise TokenVerificationError("jwks_not_configured")
        signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=[algorithm],
            audience=self.audience,
            issuer=self.issuer,
            options=self._decode_options(),
        )


@lru_cache(maxsize=1)
def get_token_verifier() -> SupabaseTokenVerifier:
    return SupabaseTokenVerifier(get_settings())


def clear_token_verifier_cache() -> None:
    get_token_verifier.cache_clear()
