"""Tests for centralized configuration."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults_are_local_development_safe() -> None:
    settings = Settings(_env_file=None, app_env="development")

    assert settings.app_name == "CivicFlow"
    assert settings.app_env == "development"
    assert settings.debug is False
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.database_url is None
    assert settings.database_url_value is None
    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    assert settings.cors_allow_credentials is True
    assert settings.service_name == "CivicFlow API"


def test_cors_origins_accept_comma_separated_values() -> None:
    settings = Settings(
        _env_file=None,
        cors_origins="http://localhost:3000, https://civicflow.example/",
    )

    assert settings.cors_origins == [
        "http://localhost:3000",
        "https://civicflow.example",
    ]


def test_cors_origins_accept_json_array() -> None:
    settings = Settings(
        _env_file=None,
        cors_origins='["https://a.example", "https://b.example"]',
    )

    assert settings.cors_origins == ["https://a.example", "https://b.example"]


def test_invalid_cors_origin_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Invalid CORS origin"):
        Settings(_env_file=None, cors_origins="not-a-url")


def test_api_prefix_is_normalized() -> None:
    settings = Settings(_env_file=None, api_v1_prefix="api/v2/")
    assert settings.api_v1_prefix == "/api/v2"


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError, match="LOG_LEVEL"):
        Settings(_env_file=None, log_level="verbose")


def test_blank_secrets_become_none() -> None:
    settings = Settings(
        _env_file=None,
        database_url="  ",
        supabase_url=" ",
        supabase_anon_key="",
        supabase_service_role_key="",
    )

    assert settings.database_url is None
    assert settings.supabase_url is None
    assert settings.supabase_anon_key is None
    assert settings.supabase_service_role_key is None


def test_secrets_are_masked_in_repr() -> None:
    secret_url = "postgresql+psycopg://user:super-secret@localhost:5432/civicflow"
    settings = Settings(_env_file=None, database_url=secret_url)

    assert settings.database_url_value == secret_url
    assert "super-secret" not in repr(settings)


def test_wildcard_cors_is_rejected_with_credentials() -> None:
    with pytest.raises(ValidationError, match="cannot contain"):
        Settings(
            _env_file=None,
            cors_origins="*",
            cors_allow_credentials=True,
        )


def test_wildcard_cors_is_allowed_without_credentials() -> None:
    settings = Settings(
        _env_file=None,
        cors_origins="*",
        cors_allow_credentials=False,
    )
    assert settings.cors_origins == ["*"]


def test_production_requires_safe_security_settings() -> None:
    with pytest.raises(ValidationError) as error_info:
        Settings(
            _env_file=None,
            app_env="production",
            debug=True,
            cors_origins="http://localhost:3000",
            database_url="postgresql+psycopg://user:pass@db:5432/civicflow",
        )

    message = str(error_info.value)
    assert "DEBUG must be false in production" in message


def test_production_requires_database_url() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL is required"):
        Settings(
            _env_file=None,
            app_env="production",
            debug=False,
            cors_origins="https://civicflow.example",
            database_url=None,
        )


def test_production_requires_cors_origins() -> None:
    with pytest.raises(ValidationError, match="CORS_ORIGINS must be explicitly"):
        Settings(
            _env_file=None,
            app_env="production",
            debug=False,
            cors_origins="",
            database_url="postgresql+psycopg://user:pass@db:5432/civicflow",
        )


def test_production_valid_configuration_loads() -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        debug=False,
        cors_origins="https://civicflow.example",
        database_url="postgresql+psycopg://user:pass@db:5432/civicflow",
        supabase_url="https://project.supabase.co",
    )

    assert settings.is_production is True
    assert settings.database_url_value is not None
    assert settings.supabase_issuer == "https://project.supabase.co/auth/v1"


def test_production_requires_supabase_url() -> None:
    with pytest.raises(ValidationError, match="SUPABASE_URL is required"):
        Settings(
            _env_file=None,
            app_env="production",
            debug=False,
            cors_origins="https://civicflow.example",
            database_url="postgresql+psycopg://user:pass@db:5432/civicflow",
            supabase_url=None,
        )


def test_jwt_audience_must_not_be_blank() -> None:
    with pytest.raises(ValidationError, match="SUPABASE_JWT_AUDIENCE"):
        Settings(_env_file=None, supabase_jwt_audience="  ")
