"""Model registry, reproducibility, and active-model resolution."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.decisions.config import DecisionConfig, DecisionConfigError
from app.models import ModelLifecycleAction, ModelVersion, ModelVersionEvent
from app.risk.config import RiskConfig, RiskConfigError


class GovernanceError(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def runtime_config(model_name: str, settings: Settings) -> tuple[dict, str]:
    if model_name == "risk":
        config = RiskConfig.from_settings(settings)
        return config.as_dict(), config.config_hash
    if model_name == "decision":
        config = DecisionConfig.from_settings(settings)
        return config.as_dict(), config.config_hash
    raise GovernanceError("Unsupported model name.", code="invalid_model_name")


def active_model(session: Session, model_name: str) -> ModelVersion | None:
    return session.scalar(
        select(ModelVersion).where(
            ModelVersion.model_name == model_name,
            ModelVersion.is_active.is_(True),
        )
    )


def register_model(
    session: Session,
    *,
    model_name: str,
    version: str,
    description: str | None,
    settings: Settings,
    actor_id: UUID | None,
) -> ModelVersion:
    config, config_hash = runtime_config(model_name, settings)
    existing = session.scalar(
        select(ModelVersion).where(
            ModelVersion.model_name == model_name,
            ModelVersion.version == version,
        )
    )
    if existing is not None:
        if existing.config_hash != config_hash:
            raise GovernanceError(
                "A model version with this name already exists with a different configuration.",
                code="model_version_conflict",
            )
        return existing
    model = ModelVersion(
        model_name=model_name,
        version=version.strip(),
        config=config,
        config_hash=config_hash,
        description=description,
        is_active=False,
        created_by=actor_id,
    )
    session.add(model)
    try:
        session.flush()
        session.add(
            ModelVersionEvent(
                model_version_id=model.id,
                action=ModelLifecycleAction.REGISTERED,
                actor_id=actor_id,
                reason="Runtime configuration registered.",
            )
        )
        session.commit()
    except IntegrityError as error:
        session.rollback()
        concurrent = session.scalar(
            select(ModelVersion).where(
                ModelVersion.model_name == model_name,
                ModelVersion.version == version,
            )
        )
        if concurrent is not None and concurrent.config_hash == config_hash:
            return concurrent
        raise GovernanceError(
            "Model registration conflicted with a concurrent change.",
            code="model_registration_conflict",
        ) from error
    session.refresh(model)
    return model


def activate_model(
    session: Session, model: ModelVersion, *, actor_id: UUID | None, reason: str | None
) -> ModelVersion:
    locked = session.scalar(
        select(ModelVersion)
        .where(ModelVersion.id == model.id)
        .with_for_update()
    )
    if locked is None:
        raise GovernanceError("Model version not found.", code="model_not_found")
    model = locked
    current = session.scalar(
        select(ModelVersion)
        .where(
            ModelVersion.model_name == model.model_name,
            ModelVersion.is_active.is_(True),
        )
        .with_for_update()
    )
    previous_id = current.id if current is not None and current.id != model.id else None
    if current is not None and current.id != model.id:
        current.is_active = False
        session.add(
            ModelVersionEvent(
                model_version_id=current.id,
                previous_model_version_id=model.id,
                action=ModelLifecycleAction.DEACTIVATED,
                actor_id=actor_id,
                reason=f"Superseded by {model.version}.",
            )
        )
        # The partial unique index permits one active model per name. Flush the
        # deactivation before activating the replacement so flush order cannot
        # transiently violate that invariant.
        session.flush()
    model.is_active = True
    model.activated_at = datetime.now(timezone.utc)
    session.add(
        ModelVersionEvent(
            model_version_id=model.id,
            previous_model_version_id=previous_id,
            action=ModelLifecycleAction.ACTIVATED,
            actor_id=actor_id,
            reason=reason,
        )
    )
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise GovernanceError(
            "Another activation changed the active model; retry with a fresh read.",
            code="model_activation_conflict",
        ) from error
    session.refresh(model)
    return model


def resolve_decision_config(
    session: Session, settings: Settings
) -> DecisionConfig:
    """Use the active decision model when registered, never silently ignoring it."""
    model = active_model(session, "decision")
    if model is None:
        return DecisionConfig.from_settings(settings)
    try:
        return DecisionConfig.from_dict(model.config)
    except (KeyError, TypeError, ValueError, DecisionConfigError) as error:
        raise DecisionConfigError(
            "The active registered decision model configuration is invalid; "
            "repair or activate a valid model before simulating."
        ) from error


def resolve_risk_config(session: Session, settings: Settings) -> RiskConfig:
    """Use the active registered model when available; otherwise runtime settings."""
    model = active_model(session, "risk")
    if model is None:
        return RiskConfig.from_settings(settings)
    try:
        return RiskConfig.from_dict(model.config)
    except (KeyError, TypeError, ValueError, RiskConfigError) as error:
        # Silently falling back would compute risk under a different model than
        # the one an administrator activated, breaking reproducibility.
        raise RiskConfigError(
            "The active registered risk model configuration is invalid; "
            "repair or activate a valid model before running risk calculations."
        ) from error
