"""Centralized application configuration.

All runtime configuration is read from environment variables (optionally loaded
from ``backend/.env``). Secrets use ``SecretStr`` so they are never rendered in
logs or repr output.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["development", "testing", "staging", "production"]

_DEFAULT_CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
_ALLOWED_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


class Settings(BaseSettings):
    """Validated application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "CivicFlow"
    app_env: Environment = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"

    # CORS
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(_DEFAULT_CORS_ORIGINS)
    )
    cors_allow_credentials: bool = True

    # Database
    database_url: SecretStr | None = None
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=50)
    database_pool_timeout_s: int = Field(default=30, ge=1, le=300)
    database_pool_recycle_s: int = Field(default=1800, ge=60)
    database_connect_timeout_s: int = Field(default=5, ge=1, le=60)
    database_sslmode: str | None = None

    # Supabase Auth / JWT verification
    supabase_url: str | None = None
    supabase_anon_key: SecretStr | None = None
    supabase_service_role_key: SecretStr | None = None
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_issuer: str | None = None
    supabase_jwks_url: str | None = None
    supabase_jwks_cache_seconds: int = Field(default=3600, ge=60, le=86400)

    # Supabase Storage (evidence)
    supabase_storage_bucket: str = "incident-evidence"
    supabase_storage_signed_url_seconds: int = Field(default=300, ge=60, le=3600)
    evidence_max_file_size_bytes: int = Field(
        default=10 * 1024 * 1024, ge=1, le=50 * 1024 * 1024
    )
    evidence_max_files_per_upload: int = Field(default=5, ge=1, le=10)

    @field_validator("app_name")
    @classmethod
    def _validate_app_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("APP_NAME must not be empty")
        return value

    @field_validator("api_v1_prefix")
    @classmethod
    def _validate_api_prefix(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("API_V1_PREFIX must not be empty")
        value = f"/{value.strip('/')}"
        if value == "/":
            raise ValueError("API_V1_PREFIX must include a version segment")
        return value

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        level = value.strip().upper()
        if level not in _ALLOWED_LOG_LEVELS:
            allowed = ", ".join(sorted(_ALLOWED_LOG_LEVELS))
            raise ValueError(f"LOG_LEVEL must be one of: {allowed}")
        return level

    @field_validator(
        "database_url",
        "supabase_anon_key",
        "supabase_service_role_key",
        mode="before",
    )
    @classmethod
    def _empty_secret_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator(
        "supabase_url", "supabase_jwt_issuer", "supabase_jwks_url", mode="before"
    )
    @classmethod
    def _empty_url_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator(
        "supabase_url", "supabase_jwt_issuer", "supabase_jwks_url"
    )
    @classmethod
    def _validate_supabase_urls(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().rstrip("/")
        if not value.startswith(("https://", "http://")):
            raise ValueError("Supabase URLs must start with http:// or https://")
        if value.startswith("http://") and "localhost" not in value and "127.0.0.1" not in value:
            raise ValueError("Supabase URLs must use HTTPS outside local development")
        return value

    @field_validator("database_sslmode")
    @classmethod
    def _validate_sslmode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        allowed = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
        if normalized not in allowed:
            raise ValueError(
                "DATABASE_SSLMODE must be one of: " + ", ".join(sorted(allowed))
            )
        return normalized

    @field_validator("supabase_storage_bucket")
    @classmethod
    def _validate_storage_bucket(cls, value: str) -> str:
        value = value.strip()
        if not value or not all(
            character.isalnum() or character in "._-" for character in value
        ):
            raise ValueError(
                "SUPABASE_STORAGE_BUCKET must contain only letters, digits, '.', '_' or '-'"
            )
        return value

    @property
    def supabase_storage_url(self) -> str | None:
        if self.supabase_url:
            return f"{self.supabase_url}/storage/v1"
        return None

    @field_validator("supabase_jwt_audience")
    @classmethod
    def _validate_audience(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("SUPABASE_JWT_AUDIENCE must not be empty")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> list[str]:
        """Accept comma-separated env values or JSON arrays."""
        if value is None:
            return []
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        "CORS_ORIGINS must be a comma-separated list or JSON array"
                    ) from exc
                if not isinstance(parsed, list):
                    raise ValueError("CORS_ORIGINS must be a list of origins")
                value = parsed
            else:
                value = raw.split(",")
        if not isinstance(value, (list, tuple)):
            raise ValueError("CORS_ORIGINS must be a list of origins")

        origins: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("Each CORS origin must be a string")
            origin = item.strip().rstrip("/")
            if not origin:
                continue
            if origin != "*" and not origin.startswith(("http://", "https://")):
                raise ValueError(
                    f"Invalid CORS origin '{origin}': expected http(s) URL or '*'"
                )
            if origin not in origins:
                origins.append(origin)
        return origins

    @model_validator(mode="after")
    def _validate_security(self) -> "Settings":
        if self.cors_allow_credentials and "*" in self.cors_origins:
            raise ValueError(
                "CORS_ORIGINS cannot contain '*' when CORS_ALLOW_CREDENTIALS is true"
            )

        if self.app_env == "production":
            problems: list[str] = []
            if self.debug:
                problems.append("DEBUG must be false in production")
            if not self.cors_origins:
                problems.append("CORS_ORIGINS must be explicitly configured in production")
            if self.database_url is None:
                problems.append("DATABASE_URL is required in production")
            if self.supabase_url is None:
                problems.append("SUPABASE_URL is required in production")
            if problems:
                raise ValueError("; ".join(problems))
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def service_name(self) -> str:
        return f"{self.app_name} API"

    @property
    def database_url_value(self) -> str | None:
        if self.database_url is None:
            return None
        return self.database_url.get_secret_value()

    @property
    def supabase_issuer(self) -> str | None:
        if self.supabase_jwt_issuer:
            return self.supabase_jwt_issuer
        if self.supabase_url:
            return f"{self.supabase_url}/auth/v1"
        return None

    @property
    def supabase_jwks_url_value(self) -> str | None:
        if self.supabase_jwks_url:
            return self.supabase_jwks_url
        if self.supabase_url:
            return f"{self.supabase_url}/auth/v1/.well-known/jwks.json"
        return None


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
