"""Centralized application configuration.

All runtime configuration is read from environment variables (optionally loaded
from ``backend/.env``). Secrets use ``SecretStr`` so they are never rendered in
logs or repr output.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, ValidationInfo, field_validator, model_validator
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

    # Production hardening (Phase 13)
    security_headers_enabled: bool = True
    api_docs_enabled: bool = True
    rate_limit_enabled: bool | None = None  # None => follows is_production
    rate_limit_requests_per_minute: int = Field(default=120, ge=10, le=10000)

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

    # Phase 4 explainable incident intelligence
    intelligence_duplicate_radius_m: int = Field(default=250, ge=10, le=5000)
    intelligence_related_radius_m: int = Field(default=1500, ge=50, le=20000)
    intelligence_duplicate_window_hours: int = Field(default=24, ge=1, le=168)
    intelligence_related_window_hours: int = Field(default=72, ge=1, le=720)
    intelligence_candidate_limit: int = Field(default=100, ge=1, le=500)
    intelligence_duplicate_text_threshold: float = Field(
        default=0.30, ge=0.0, le=1.0
    )
    intelligence_duplicate_confidence_threshold: float = Field(
        default=0.55, ge=0.0, le=1.0
    )
    intelligence_related_confidence_threshold: float = Field(
        default=0.42, ge=0.0, le=1.0
    )
    intelligence_infrastructure_radius_m: int = Field(
        default=1000, ge=50, le=10000
    )
    intelligence_impact_depth: int = Field(default=2, ge=1, le=4)
    intelligence_impact_limit: int = Field(default=20, ge=1, le=100)

    # Phase 5 urban risk engine
    risk_model_version: str = "risk-v1"
    risk_min_resolution: int = Field(default=7, ge=5, le=10)
    risk_max_resolution: int = Field(default=10, ge=5, le=12)
    risk_default_resolution: int = Field(default=8, ge=5, le=12)
    risk_default_window_hours: int = Field(default=168, ge=1, le=8760)
    risk_max_window_hours: int = Field(default=2160, ge=1, le=8760)
    risk_recency_half_life_hours: int = Field(default=72, ge=1, le=720)
    risk_density_saturation: int = Field(default=20, ge=1, le=1000)
    risk_infrastructure_radius_m: int = Field(default=750, ge=50, le=5000)
    risk_max_incidents: int = Field(default=20000, ge=100, le=100000)
    risk_max_cells: int = Field(default=500, ge=10, le=2000)
    risk_privacy_min_incidents: int = Field(default=3, ge=1, le=20)
    risk_trend_min_incidents: int = Field(default=3, ge=2, le=20)
    risk_weight_severity: float = Field(default=0.24, ge=0.0, le=1.0)
    risk_weight_density: float = Field(default=0.13, ge=0.0, le=1.0)
    risk_weight_spatial: float = Field(default=0.07, ge=0.0, le=1.0)
    risk_weight_recency: float = Field(default=0.14, ge=0.0, le=1.0)
    risk_weight_active: float = Field(default=0.08, ge=0.0, le=1.0)
    risk_weight_category: float = Field(default=0.08, ge=0.0, le=1.0)
    risk_weight_trend: float = Field(default=0.06, ge=0.0, le=1.0)
    risk_weight_infrastructure: float = Field(default=0.14, ge=0.0, le=1.0)
    risk_weight_dependency: float = Field(default=0.06, ge=0.0, le=1.0)
    risk_threshold_low: float = Field(default=20.0, ge=0.0, le=100.0)
    risk_threshold_moderate: float = Field(default=40.0, ge=0.0, le=100.0)
    risk_threshold_high: float = Field(default=65.0, ge=0.0, le=100.0)
    risk_threshold_critical: float = Field(default=85.0, ge=0.0, le=100.0)
    decision_model_version: str = "decision-v1"
    decision_min_horizon_minutes: int = Field(default=60, ge=1, le=10080)
    decision_max_horizon_minutes: int = Field(default=10080, ge=1, le=10080)
    decision_max_actions: int = Field(default=200, ge=1, le=1000)
    decision_max_resources: int = Field(default=200, ge=1, le=1000)
    decision_solver_time_limit_ms: int = Field(default=1500, ge=50, le=10000)
    decision_default_risk_window_hours: int = Field(default=168, ge=1, le=2160)
    decision_default_resolution: int = Field(default=8, ge=7, le=10)
    decision_weight_risk_reduction: float = Field(default=0.45, ge=0.0, le=1.0)
    decision_weight_action_coverage: float = Field(default=0.25, ge=0.0, le=1.0)
    decision_weight_cost_efficiency: float = Field(default=0.15, ge=0.0, le=1.0)
    decision_weight_time_efficiency: float = Field(default=0.15, ge=0.0, le=1.0)

    # Phase 8 empirical validation
    validation_max_records: int = Field(default=10000, ge=100, le=50000)
    validation_max_folds: int = Field(default=8, ge=2, le=24)
    validation_target_hours: int = Field(default=168, ge=24, le=720)
    validation_history_hours: int = Field(default=672, ge=168, le=2160)
    validation_top_k: int = Field(default=10, ge=5, le=100)
    validation_resolution: int = Field(default=9, ge=7, le=9)

    # Weather-aware incident intelligence (declared challenges A02 + A06).
    # The default provider has a free non-commercial tier and needs no key.
    weather_enabled: bool = True
    weather_provider: Literal["open-meteo", "mock"] = "open-meteo"
    weather_api_base_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_api_key: SecretStr | None = None
    # Keyless fallback used when the primary provider rate-limits us. MET
    # Norway's Locationforecast is free and needs no API key.
    weather_fallback_enabled: bool = True
    weather_fallback_base_url: str = (
        "https://api.met.no/weatherapi/locationforecast/2.0/compact"
    )
    weather_timeout_s: float = Field(default=8.0, ge=1.0, le=60.0)
    weather_max_retries: int = Field(default=2, ge=0, le=5)
    weather_retry_backoff_s: float = Field(default=0.5, ge=0.0, le=10.0)
    weather_cache_ttl_minutes: int = Field(default=30, ge=0, le=1440)
    weather_forecast_hours: int = Field(default=12, ge=1, le=48)
    weather_rule_heavy_rain_mm: float = Field(default=5.0, ge=0.0, le=200.0)
    weather_rule_rain_probability_pct: int = Field(default=60, ge=0, le=100)
    weather_rule_strong_wind_kmh: float = Field(default=35.0, ge=0.0, le=200.0)
    weather_rule_strong_gust_kmh: float = Field(default=50.0, ge=0.0, le=300.0)
    weather_rule_high_temperature_c: float = Field(
        default=35.0, ge=-50.0, le=70.0
    )

    # Civic AI assistant. The key is optional; when absent the API returns
    # deterministic, clearly-labelled local summaries instead.
    groq_api_key: SecretStr | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_s: float = Field(default=15.0, ge=1.0, le=60.0)

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
        "weather_api_key",
        "groq_api_key",
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

    @field_validator("weather_api_base_url", "weather_fallback_base_url")
    @classmethod
    def _validate_weather_url(cls, value: str, info: ValidationInfo) -> str:
        name = info.field_name.upper()
        value = value.strip().rstrip("/")
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"{name} must be an http(s) URL")
        if parsed.scheme == "http" and "localhost" not in parsed.netloc and "127.0.0.1" not in parsed.netloc:
            raise ValueError(f"{name} must use HTTPS outside local development")
        return value

    @field_validator("groq_base_url")
    @classmethod
    def _validate_groq_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("GROQ_BASE_URL must be an https URL")
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
    def _validate_risk_bounds(self) -> "Settings":
        if not self.risk_min_resolution <= self.risk_default_resolution <= self.risk_max_resolution:
            raise ValueError(
                "RISK_DEFAULT_RESOLUTION must be between RISK_MIN_RESOLUTION "
                "and RISK_MAX_RESOLUTION"
            )
        if self.risk_default_window_hours > self.risk_max_window_hours:
            raise ValueError(
                "RISK_DEFAULT_WINDOW_HOURS must be <= RISK_MAX_WINDOW_HOURS"
            )
        if not (
            self.decision_min_horizon_minutes
            <= self.decision_max_horizon_minutes
        ):
            raise ValueError(
                "DECISION_MIN_HORIZON_MINUTES must be <= "
                "DECISION_MAX_HORIZON_MINUTES"
            )
        decision_weights = {
            "risk_reduction": self.decision_weight_risk_reduction,
            "action_coverage": self.decision_weight_action_coverage,
            "cost_efficiency": self.decision_weight_cost_efficiency,
            "time_efficiency": self.decision_weight_time_efficiency,
        }
        if abs(sum(decision_weights.values()) - 1.0) > 1e-6:
            raise ValueError("DECISION_* weights must sum to 1.0")
        weights = {
            "severity": self.risk_weight_severity,
            "density": self.risk_weight_density,
            "spatial": self.risk_weight_spatial,
            "recency": self.risk_weight_recency,
            "active": self.risk_weight_active,
            "category": self.risk_weight_category,
            "trend": self.risk_weight_trend,
            "infrastructure": self.risk_weight_infrastructure,
            "dependency": self.risk_weight_dependency,
        }
        if abs(sum(weights.values()) - 1.0) > 1e-6:
            raise ValueError("RISK_WEIGHT_* values must sum to 1.0")
        thresholds = [
            self.risk_threshold_low,
            self.risk_threshold_moderate,
            self.risk_threshold_high,
            self.risk_threshold_critical,
        ]
        if thresholds != sorted(thresholds) or len(set(thresholds)) != len(thresholds):
            raise ValueError(
                "RISK_THRESHOLD_* values must be strictly ascending"
            )
        if thresholds[0] <= 0 or thresholds[-1] >= 100:
            raise ValueError(
                "RISK_THRESHOLD_* values must be within (0, 100)"
            )
        return self

    @model_validator(mode="after")
    def _validate_intelligence_bounds(self) -> "Settings":
        if self.intelligence_related_radius_m < self.intelligence_duplicate_radius_m:
            raise ValueError(
                "INTELLIGENCE_RELATED_RADIUS_M must be >= "
                "INTELLIGENCE_DUPLICATE_RADIUS_M"
            )
        if (
            self.intelligence_related_window_hours
            < self.intelligence_duplicate_window_hours
        ):
            raise ValueError(
                "INTELLIGENCE_RELATED_WINDOW_HOURS must be >= "
                "INTELLIGENCE_DUPLICATE_WINDOW_HOURS"
            )
        return self

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
    def rate_limiting_active(self) -> bool:
        """Rate limiting is on in production unless explicitly overridden."""
        if self.rate_limit_enabled is None:
            return self.is_production
        return self.rate_limit_enabled

    @property
    def docs_effective_enabled(self) -> bool:
        """Interactive API docs are disabled by default in production."""
        if self.is_production:
            return self.api_docs_enabled and self.debug
        return self.api_docs_enabled

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
