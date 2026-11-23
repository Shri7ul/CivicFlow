"""Private Supabase Storage client for incident evidence."""

from __future__ import annotations

from urllib.parse import quote

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger("storage")


class StorageService:
    """Server-only Storage adapter.

    The service-role key is used only on the backend. Bucket creation is lazy
    so a deployment can recover if the bucket was removed after migrations.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client
        self._bucket_checked = False

    @property
    def _service_key(self) -> str:
        key = self.settings.supabase_service_role_key
        if key is None or not key.get_secret_value():
            raise AppError(
                "Evidence storage is not configured.",
                status_code=503,
                code="evidence_storage_unavailable",
            )
        return key.get_secret_value()

    @property
    def _storage_url(self) -> str:
        if not self.settings.supabase_storage_url:
            raise AppError(
                "Evidence storage is not configured.",
                status_code=503,
                code="evidence_storage_unavailable",
            )
        return self.settings.supabase_storage_url

    @property
    def bucket(self) -> str:
        return self.settings.supabase_storage_bucket

    def _headers(self) -> dict[str, str]:
        key = self._service_key
        return {
            "Authorization": f"Bearer {key}",
            "apikey": key,
        }

    def _http(self, *, timeout: float = 60.0) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=timeout)

    def _object_url(self, path: str) -> str:
        encoded_bucket = quote(self.bucket, safe="")
        encoded_path = quote(path, safe="/")
        return (
            f"{self._storage_url}/object/{encoded_bucket}/{encoded_path}"
        )

    def _ensure_bucket(self, client: httpx.Client) -> None:
        if self._bucket_checked:
            return
        response = client.post(
            f"{self._storage_url}/bucket",
            headers={
                **self._headers(),
                "Content-Type": "application/json",
            },
            json={
                "id": self.bucket,
                "name": self.bucket,
                "public": False,
                "file_size_limit": self.settings.evidence_max_file_size_bytes,
                "allowed_mime_types": [
                    "image/jpeg",
                    "image/png",
                    "image/webp",
                ],
            },
        )
        # A concurrently-created bucket is not an error.
        if response.status_code not in (200, 201, 409):
            logger.warning(
                "Storage bucket creation failed | status=%s", response.status_code
            )
            raise AppError(
                "Evidence storage is temporarily unavailable.",
                status_code=503,
                code="evidence_storage_unavailable",
            )
        self._bucket_checked = True

    def upload(self, path: str, data: bytes, mime_type: str) -> None:
        client = self._http()
        try:
            for attempt in range(2):
                response = client.post(
                    self._object_url(path),
                    headers={
                        **self._headers(),
                        "Content-Type": mime_type,
                        "x-upsert": "false",
                        "Cache-Control": "3600",
                    },
                    content=data,
                )
                if response.status_code in (200, 201):
                    return
                if response.status_code == 404 and attempt == 0:
                    self._ensure_bucket(client)
                    continue
                logger.warning(
                    "Storage upload failed | status=%s", response.status_code
                )
                raise AppError(
                    "Evidence storage rejected the upload.",
                    status_code=503,
                    code="evidence_storage_unavailable",
                )
            raise AppError(
                "Evidence storage rejected the upload.",
                status_code=503,
                code="evidence_storage_unavailable",
            )
        except AppError:
            raise
        except httpx.HTTPError as exc:
            logger.warning("Storage upload error | type=%s", type(exc).__name__)
            raise AppError(
                "Evidence storage is temporarily unavailable.",
                status_code=503,
                code="evidence_storage_unavailable",
            ) from exc
        finally:
            if self._client is None:
                client.close()

    def delete(self, path: str) -> None:
        """Best-effort cleanup; never mask the original request error."""
        client = self._http(timeout=20.0)
        try:
            response = client.delete(
                self._object_url(path),
                headers=self._headers(),
            )
            if response.status_code not in (200, 204, 404):
                logger.warning(
                    "Storage delete failed | status=%s", response.status_code
                )
        except httpx.HTTPError as exc:
            logger.warning("Storage delete error | type=%s", type(exc).__name__)
        finally:
            if self._client is None:
                client.close()

    def create_signed_url(self, path: str) -> str:
        client = self._http(timeout=30.0)
        try:
            response = client.post(
                f"{self._storage_url}/object/sign/{quote(self.bucket, safe='')}/"
                f"{quote(path, safe='/')}",
                headers={
                    **self._headers(),
                    "Content-Type": "application/json",
                },
                json={"expiresIn": self.settings.supabase_storage_signed_url_seconds},
            )
            if response.status_code not in (200, 201):
                logger.warning(
                    "Storage signing failed | status=%s", response.status_code
                )
                raise AppError(
                    "Evidence preview is temporarily unavailable.",
                    status_code=503,
                    code="evidence_storage_unavailable",
                )
            payload = response.json()
            signed = payload.get("signedURL") or payload.get("signedUrl")
            if not isinstance(signed, str) or not signed:
                raise AppError(
                    "Evidence preview is temporarily unavailable.",
                    status_code=503,
                    code="evidence_storage_unavailable",
                )
            if signed.startswith(("http://", "https://")):
                return signed
            prefix = f"{self._storage_url}"
            if signed.startswith("/object/"):
                return f"{prefix}{signed}"
            return f"{prefix}/{signed.lstrip('/')}"
        except AppError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Storage signing error | type=%s", type(exc).__name__)
            raise AppError(
                "Evidence preview is temporarily unavailable.",
                status_code=503,
                code="evidence_storage_unavailable",
            ) from exc
        finally:
            if self._client is None:
                client.close()

    def healthcheck(self) -> bool:
        client = self._http(timeout=10.0)
        try:
            response = client.get(
                f"{self._storage_url}/bucket",
                headers=self._headers(),
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False
        finally:
            if self._client is None:
                client.close()


def get_storage_service() -> StorageService:
    """FastAPI dependency; overridable in tests."""
    return StorageService()
