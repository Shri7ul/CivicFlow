"""Incident evidence validation, upload orchestration, and safe serialization."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Sequence

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import AuthenticatedUser
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.models import IncidentEvidence
from app.schemas.incidents import EvidenceResponse, EvidenceUrlResponse, ProfileSummary
from app.services.incidents import get_incident
from app.services.storage import StorageService

logger = get_logger("evidence")

_ALLOWED_TYPES: dict[str, tuple[str, str]] = {
    "image/jpeg": ("jpeg", "jpg"),
    "image/png": ("png", "png"),
    "image/webp": ("webp", "webp"),
}
_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._ ()\[\]-]+")


def _settings() -> Settings:
    return get_settings()


def detect_mime(data: bytes) -> str:
    """Detect an allowed image type from bytes, never from client metadata."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if (
        len(data) >= 12
        and data[:4] == b"RIFF"
        and data[8:12] == b"WEBP"
    ):
        return "image/webp"
    raise AppError(
        "Only JPEG, PNG, and WebP images are accepted.",
        status_code=422,
        code="unsupported_evidence_type",
    )


def sanitize_filename(value: str | None) -> str:
    name = (value or "evidence").replace("\\", "/").split("/")[-1]
    name = "".join(
        character
        for character in name
        if character.isprintable() and character not in "\x00\r\n\t"
    )
    name = _UNSAFE_FILENAME.sub("_", name).strip(" .")
    if not name:
        name = "evidence"
    return name[:255]


def _validate_size(data: bytes, settings: Settings) -> None:
    if not data:
        raise AppError(
            "An evidence file cannot be empty.",
            status_code=422,
            code="empty_evidence_file",
        )
    if len(data) > settings.evidence_max_file_size_bytes:
        raise AppError(
            f"Each evidence file must be at most "
            f"{settings.evidence_max_file_size_bytes // (1024 * 1024)} MB.",
            status_code=413,
            code="evidence_too_large",
        )


def _read_and_validate(
    file: UploadFile, settings: Settings
) -> tuple[str, str, bytes, str]:
    filename = sanitize_filename(file.filename)
    data = file.file.read(settings.evidence_max_file_size_bytes + 1)
    _validate_size(data, settings)
    mime_type = detect_mime(data)
    extension = _ALLOWED_TYPES[mime_type][1]
    return filename, mime_type, data, extension


def serialize_evidence(evidence: IncidentEvidence) -> EvidenceResponse:
    return EvidenceResponse(
        id=evidence.id,
        incident_id=evidence.incident_id,
        file_name=evidence.file_name,
        mime_type=evidence.mime_type,
        file_size=evidence.file_size,
        uploader=ProfileSummary(
            id=evidence.uploader.id,
            full_name=evidence.uploader.full_name,
        ),
        created_at=evidence.created_at,
    )


def list_evidence(
    session: Session,
    *,
    user: AuthenticatedUser,
    incident_id: uuid.UUID,
) -> list[EvidenceResponse]:
    get_incident(session, incident_id, user)
    evidence = session.scalars(
        select(IncidentEvidence)
        .options(joinedload(IncidentEvidence.uploader))
        .where(IncidentEvidence.incident_id == incident_id)
        .order_by(IncidentEvidence.created_at.asc(), IncidentEvidence.id.asc())
    ).all()
    return [serialize_evidence(item) for item in evidence]


def evidence_signed_url(
    session: Session,
    *,
    user: AuthenticatedUser,
    incident_id: uuid.UUID,
    evidence_id: uuid.UUID,
    storage: StorageService,
) -> EvidenceUrlResponse:
    get_incident(session, incident_id, user)
    evidence = session.scalar(
        select(IncidentEvidence).where(
            IncidentEvidence.id == evidence_id,
            IncidentEvidence.incident_id == incident_id,
        )
    )
    if evidence is None:
        raise AppError(
            "Evidence not found.",
            status_code=404,
            code="evidence_not_found",
        )
    settings = _settings()
    signed_url = storage.create_signed_url(evidence.storage_path)
    return EvidenceUrlResponse(
        signed_url=signed_url,
        expires_in=settings.supabase_storage_signed_url_seconds,
    )


def upload_evidence(
    session: Session,
    *,
    user: AuthenticatedUser,
    incident_id: uuid.UUID,
    files: Sequence[UploadFile],
    storage: StorageService,
) -> list[EvidenceResponse]:
    settings = _settings()
    if not files:
        raise AppError(
            "Select at least one evidence file.",
            status_code=422,
            code="evidence_required",
        )
    if len(files) > settings.evidence_max_files_per_upload:
        raise AppError(
            f"Upload at most {settings.evidence_max_files_per_upload} files at once.",
            status_code=422,
            code="too_many_evidence_files",
        )

    get_incident(session, incident_id, user)

    validated: list[tuple[str, str, bytes, str]] = []
    for file in files:
        validated.append(_read_and_validate(file, settings))

    uploaded_paths: list[str] = []
    records: list[IncidentEvidence] = []
    try:
        for filename, mime_type, data, extension in validated:
            storage_path = f"{incident_id}/{uuid.uuid4().hex}.{extension}"
            try:
                storage.upload(storage_path, data, mime_type)
            except AppError:
                raise
            except Exception as exc:
                raise AppError(
                    "Evidence storage is temporarily unavailable.",
                    status_code=503,
                    code="evidence_storage_unavailable",
                ) from exc
            uploaded_paths.append(storage_path)
            records.append(
                IncidentEvidence(
                    incident_id=incident_id,
                    uploaded_by=user.profile.id,
                    storage_path=storage_path,
                    file_name=filename,
                    mime_type=mime_type,
                    file_size=len(data),
                    created_at=datetime.now(timezone.utc),
                    uploader=user.profile,
                )
            )
        session.add_all(records)
        session.commit()
    except Exception:
        session.rollback()
        for path in uploaded_paths:
            storage.delete(path)
        raise

    logger.info(
        "Uploaded %s evidence file(s) | incident=%s",
        len(records),
        incident_id,
    )
    return [serialize_evidence(record) for record in records]
