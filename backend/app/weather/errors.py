"""Weather provider failures. These never leak raw provider bodies or keys."""

from __future__ import annotations


class WeatherProviderError(Exception):
    """A provider request failed or returned unusable data.

    ``code`` is a stable machine-readable value persisted with the assessment.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def invalid_coordinates() -> WeatherProviderError:
    return WeatherProviderError(
        "invalid_coordinates", "The incident has no valid coordinates for a weather lookup."
    )


def provider_unavailable(detail: str = "") -> WeatherProviderError:
    message = "The weather provider could not be reached."
    return WeatherProviderError("provider_unavailable", f"{message} {detail}".strip())


def provider_timeout() -> WeatherProviderError:
    return WeatherProviderError(
        "provider_timeout", "The weather provider did not respond in time."
    )


def rate_limited() -> WeatherProviderError:
    return WeatherProviderError(
        "provider_rate_limited", "The weather provider rate limit was reached."
    )


def malformed_response() -> WeatherProviderError:
    return WeatherProviderError(
        "malformed_response", "The weather provider returned an unparseable response."
    )
