"""Storage adapter URL, upload, and failure behavior tests."""

from __future__ import annotations

import httpx
import pytest

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.services.storage import StorageService


def _settings() -> Settings:
    return Settings(
        supabase_url="https://project.supabase.co",
        supabase_service_role_key="service-role-test",
    )


def test_upload_creates_bucket_once_then_retries() -> None:
    calls: list[tuple[str, str]] = []
    first_a = True

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal first_a
        calls.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path.endswith("/bucket"):
            return httpx.Response(200, json={})
        if request.method == "POST" and "object/" in request.url.path:
            if request.url.path.endswith("/a.png") and first_a:
                first_a = False
                return httpx.Response(404, json={"error": "Bucket not found"})
            return httpx.Response(200, json={})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        service = StorageService(_settings(), client=client)
        service.upload("a.png", b"data", "image/png")
        service.upload("b.png", b"data", "image/png")
    finally:
        client.close()

    assert ("POST", "/storage/v1/bucket") in calls
    assert calls.count(("POST", "/storage/v1/object/incident-evidence/a.png")) == 2
    assert calls.count(("POST", "/storage/v1/object/incident-evidence/b.png")) == 1


def test_signing_uses_encoded_object_path_and_returns_absolute_url() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"signedURL": "/object/sign/incident-evidence/a%20b.png?token=abc"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        service = StorageService(_settings(), client=client)
        url = service.create_signed_url("incident/one image.png")
    finally:
        client.close()

    assert url == (
        "https://project.supabase.co/storage/v1"
        "/object/sign/incident-evidence/a%20b.png?token=abc"
    )
    assert seen[0].url.raw_path.decode() == (
        "/storage/v1/object/sign/incident-evidence/incident/one%20image.png"
    )
    assert "service-role-test" not in str(seen[0].url)


def test_storage_without_service_key_is_unavailable() -> None:
    service = StorageService(
        Settings(supabase_url="https://project.supabase.co")
    )
    with pytest.raises(AppError) as error:
        service.upload("a.png", b"data", "image/png")
    assert error.value.status_code == 503
    assert error.value.code == "evidence_storage_unavailable"


def test_storage_delete_is_best_effort() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        service = StorageService(_settings(), client=client)
        service.delete("a.png")
    finally:
        client.close()
