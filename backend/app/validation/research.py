"""Phase 9 research orchestration: external datasets, diagnostics, ablations.

Every record persisted here is derived from a pinned public NYC 311 snapshot and
the currently registered risk configuration. Nothing in this module mutates the
risk model, activates a configuration, or writes to operational tables.

The evidence is empirical-observational: the target is next-window public
complaint activity, not verified municipal impact or hazard ground truth.
"""

from __future__ import annotations

import statistics
import time
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import (
    ValidationDataset,
    ValidationEvidenceKind,
    ValidationExperiment,
    ValidationExperimentType,
    ValidationStatus,
)
from app.risk.config import RiskConfig
from app.validation.ablations import run_ablation_suite, variant_config
from app.validation.dataset import NYC311_BBOX, NYC311_DATASET_KEY
from app.validation.diagnostics import run_diagnostic_audit
from app.validation.risk import run_risk_backtest
from app.validation.robustness import run_robustness_suite
from app.validation.service import (
    ValidationError,
    _complete_experiment,
    _fail_experiment,
    _new_experiment,
    dataset_records,
    resolve_risk_config,
)
from app.validation.stats import bootstrap_mean_ci, paired_comparison

PHASE9_PROTOCOL = "phase9-risk-diagnosis-v1"
PHASE9_DEVELOPMENT_DATASET = NYC311_DATASET_KEY
PHASE9_METHOD = (
    "multi-region rolling-origin temporal holdout with factor diagnostics, "
    "ablation, and robustness checks"
)
PHASE9_SPLIT_METHOD = "rolling_origin_temporal_holdout"
PHASE9_EVIDENCE_KIND = ValidationEvidenceKind.EMPIRICAL_OBSERVATIONAL
BASELINE_METHODS = (
    "baseline_count",
    "baseline_recent",
    "baseline_weighted",
    "baseline_persistence",
)
CORE_TYPES = (
    ValidationExperimentType.RISK_BACKTEST,
    ValidationExperimentType.RISK_TEMPORAL,
    ValidationExperimentType.RISK_GEOGRAPHIC,
)
ABLATION_VARIANT = "factor_ablation"
DIAGNOSTIC_VARIANT = "factor_audit"
ROBUSTNESS_VARIANT = "sensitivity_suite"
FULL_VARIANT = "full"
PHASE9_MAX_DATASET_KEYS = 8
PHASE9_MAX_DATASET_KEY_LENGTH = 200
PHASE9_EXPERIMENT_READ_LIMIT = 200


def _round(value, digits: int = 6):
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def dataset_bbox(
    dataset: ValidationDataset, metadata: dict
) -> tuple[float, float, float, float]:
    value = (
        metadata.get("bbox")
        or (metadata.get("query") or {}).get("bbox")
        or dataset.dataset_metadata.get("bbox")
        or list(NYC311_BBOX)
    )
    try:
        bbox = tuple(float(item) for item in value)
    except (TypeError, ValueError) as error:
        raise ValidationError(
            "Dataset bbox metadata is invalid.", code="dataset_bbox_invalid"
        ) from error
    if len(bbox) != 4:
        raise ValidationError(
            "Dataset bbox metadata must contain four coordinates.",
            code="dataset_bbox_invalid",
        )
    return bbox  # type: ignore[return-value]


def _experiment_type(dataset: ValidationDataset) -> ValidationExperimentType:
    """Classify by geography and period, independent of the pinned snapshot."""
    if dataset.dataset_key == PHASE9_DEVELOPMENT_DATASET:
        return ValidationExperimentType.RISK_BACKTEST
    if "brooklyn" in dataset.dataset_key:
        return ValidationExperimentType.RISK_TEMPORAL
    return ValidationExperimentType.RISK_GEOGRAPHIC


def _persist(
    session: Session,
    dataset: ValidationDataset,
    *,
    experiment_type: ValidationExperimentType,
    variant_key: str,
    name: str,
    method: str,
    metrics: dict,
    baselines: dict,
    findings: list[str],
    limitations: list[str],
    reproducibility: dict,
    actor_id: uuid.UUID | None,
    config: RiskConfig,
) -> ValidationExperiment:
    experiment = _new_experiment(
        session,
        experiment_type=experiment_type,
        evidence_kind=PHASE9_EVIDENCE_KIND,
        name=name,
        method=method,
        dataset=dataset,
        actor_id=actor_id,
        model_name="risk",
        model_version=config.model_version,
        config_hash=config.config_hash,
        split_method=PHASE9_SPLIT_METHOD,
        region=dataset.region,
        period_start=dataset.period_start,
        period_end=dataset.period_end,
        record_count=metrics.get("record_count", 0),
        protocol_key=PHASE9_PROTOCOL,
        variant_key=variant_key,
    )
    try:
        return _complete_experiment(
            session,
            experiment,
            status=ValidationStatus.COMPLETED
            if metrics.get("status") == "COMPLETED"
            else ValidationStatus.INSUFFICIENT_DATA,
            metrics=metrics,
            baselines=baselines,
            findings=findings,
            limitations=limitations,
            reproducibility=reproducibility,
        )
    except Exception as error:
        _fail_experiment(session, experiment, error)
        raise


def _fold_values(result: dict, method: str, metric: str) -> list[float]:
    values = []
    for fold in result.get("folds", []):
        value = ((fold.get("metrics") or {}).get(method) or {}).get(metric)
        if value is not None:
            values.append(float(value))
    return values


def _statistics(result: dict, config: RiskConfig) -> dict:
    intervals = {}
    for metric in ("pr_auc", "roc_auc", "precision_at_k", "recall_at_k"):
        values = _fold_values(result, "civicflow_risk", metric)
        if values:
            intervals[metric] = bootstrap_mean_ci(values)
    baselines = {}
    risk_values = _fold_values(result, "civicflow_risk", "pr_auc")
    for method in BASELINE_METHODS:
        baseline_values = _fold_values(result, method, "pr_auc")
        if not risk_values or not baseline_values:
            continue
        deltas = [
            round(risk - baseline, 6)
            for risk, baseline in zip(risk_values, baseline_values)
        ]
        baselines[method] = paired_comparison(deltas)
    return {
        "fold_intervals": intervals,
        "paired_pr_auc_vs_baselines": baselines,
        "config_hash": config.config_hash,
        "evaluation_unit": "rolling_origin_fold",
        "method": (
            "percentile bootstrap over fold-level metrics and paired fold "
            "deltas; intervals are descriptive because origins overlap."
        ),
    }


def _select_candidate(ablation: dict, dataset_key: str) -> dict:
    """Pre-registered selection rule applied only to the development dataset."""
    variants = [
        item
        for item in (ablation.get("variants") or [])
        if item.get("kind") == "leave_one_out"
        and (item.get("metrics") or {}).get("pr_auc") is not None
    ]
    rule = (
        "Leave-one-out variant with the highest mean paired PR-AUC delta versus "
        "the full model on the development dataset, accepted only when that "
        "mean delta is positive. External datasets never inform selection."
    )
    if not variants:
        return {
            "candidate_key": None,
            "selection_dataset": dataset_key,
            "rule": rule,
            "reason": "No completed leave-one-out variant was persisted.",
            "selection_statistics": None,
            "removed_factors": [],
            "weights": {},
        }
    ranked = sorted(
        variants,
        key=lambda item: (item.get("delta_pr_auc") or {}).get("mean_delta") or -9.0,
        reverse=True,
    )
    best = ranked[0]
    delta = best.get("delta_pr_auc") or {}
    if delta.get("mean_delta") is None or delta["mean_delta"] <= 0:
        return {
            "candidate_key": None,
            "selection_dataset": dataset_key,
            "rule": rule,
            "reason": (
                "No leave-one-out variant improved mean paired PR-AUC on the "
                "development dataset."
            ),
            "selection_statistics": delta,
            "removed_factors": [],
            "weights": {},
        }
    return {
        "candidate_key": best["variant_key"],
        "selection_dataset": dataset_key,
        "rule": rule,
        "reason": "Pre-registered rule selected this leave-one-out variant.",
        "selection_statistics": delta,
        "removed_factors": best.get("removed_factors") or [],
        "weights": best.get("weights") or {},
    }


def _evaluate_candidate(
    *,
    records: list[dict],
    settings: Settings,
    config: RiskConfig,
    selection: dict,
    dataset_key: str,
    bbox: tuple[float, float, float, float],
    base: dict,
    sample: str,
) -> dict:
    variant = {
        "key": selection["candidate_key"],
        "kind": "candidate",
        "removed": selection["removed_factors"],
        "only": [],
    }
    candidate_config = variant_config(config, variant, selection["candidate_key"])
    result = run_risk_backtest(
        records,
        settings=settings,
        config=candidate_config,
        dataset_key=dataset_key,
        bbox=bbox,
        include_sensitivity=False,
    )
    metrics = (result.get("methods") or {}).get("civicflow_risk", {})
    reference = (base.get("methods") or {}).get("civicflow_risk", {})
    pr_deltas = [
        round(candidate - reference_value, 6)
        for candidate, reference_value in zip(
            _fold_values(result, "civicflow_risk", "pr_auc"),
            _fold_values(base, "civicflow_risk", "pr_auc"),
        )
    ]
    roc_deltas = [
        round(candidate - reference_value, 6)
        for candidate, reference_value in zip(
            _fold_values(result, "civicflow_risk", "roc_auc"),
            _fold_values(base, "civicflow_risk", "roc_auc"),
        )
    ]
    return {
        "status": result.get("status"),
        "sample": sample,
        "candidate_key": selection["candidate_key"],
        "selection_dataset": selection["selection_dataset"],
        "selection_rule": selection["rule"],
        "selection_statistics": selection.get("selection_statistics"),
        "removed_factors": selection["removed_factors"],
        "weights": dict(candidate_config.weights),
        "model_version": candidate_config.model_version,
        "config_hash": candidate_config.config_hash,
        "fold_count": len(result.get("folds", [])),
        "metrics": metrics,
        "reference_metrics": reference,
        "delta_pr_auc": paired_comparison(pr_deltas),
        "delta_roc_auc": paired_comparison(roc_deltas),
        "activated": False,
        "limitations": [
            "The candidate is evaluation-only; no risk configuration was "
            "registered or activated by this experiment.",
            "Folds overlap in time and are not independent samples.",
            "The development dataset supplies selection; external datasets "
            "are reported separately as holdouts.",
        ],
    }


def _datasets(
    session: Session, dataset_keys: list[str] | None
) -> list[ValidationDataset]:
    datasets = list(
        session.scalars(
            select(ValidationDataset).order_by(ValidationDataset.created_at)
        ).all()
    )
    if dataset_keys:
        wanted = set(dict.fromkeys(dataset_keys))
        available = {item.dataset_key for item in datasets}
        missing = sorted(wanted - available)
        if missing:
            raise ValidationError(
                f"Unknown validation dataset(s): {', '.join(missing)}",
                code="dataset_not_found",
            )
        datasets = [item for item in datasets if item.dataset_key in wanted]
    if not datasets:
        raise ValidationError(
            "No registered validation datasets are available.",
            code="dataset_not_found",
        )
    # The development dataset runs first so its ablation can seed selection
    # before any external holdout is evaluated.
    datasets.sort(
        key=lambda item: (
            item.dataset_key != PHASE9_DEVELOPMENT_DATASET,
            item.dataset_key,
        )
    )
    return datasets


def run_phase9_research(
    session: Session,
    *,
    settings: Settings,
    actor_id: uuid.UUID | None,
    dataset_keys: list[str] | None = None,
) -> dict:
    started = time.perf_counter()
    if dataset_keys is not None:
        if len(dataset_keys) > PHASE9_MAX_DATASET_KEYS:
            raise ValidationError(
                f"At most {PHASE9_MAX_DATASET_KEYS} dataset keys may be requested "
                "per run.",
                code="too_many_datasets",
            )
        if any(len(key) > PHASE9_MAX_DATASET_KEY_LENGTH for key in dataset_keys):
            raise ValidationError(
                "Dataset key exceeds the supported length.", code="invalid_dataset_key"
            )
    config = resolve_risk_config(session, settings)
    datasets = _datasets(session, dataset_keys)
    selection: dict | None = _selection_from_session(session)
    for dataset in datasets:
        records, metadata = dataset_records(session, dataset)
        if len(records) > settings.validation_max_records:
            raise ValidationError(
                "Dataset exceeds the configured validation record cap.",
                code="validation_dataset_too_large",
            )
        bbox = dataset_bbox(dataset, metadata)
        base = run_risk_backtest(
            records,
            settings=settings,
            config=config,
            dataset_key=dataset.dataset_key,
            bbox=bbox,
            include_sensitivity=True,
            include_cell_data=True,
        )
        base["record_count"] = len(records)
        base["statistics"] = _statistics(base, config)
        experiment_type = _experiment_type(dataset)
        reproducibility = {
            "dataset_key": dataset.dataset_key,
            "dataset_snapshot_sha256": dataset.snapshot_sha256,
            "dataset_bbox": list(bbox),
            "dataset_metadata": metadata,
            "risk_config": config.as_dict(),
            "risk_config_hash": config.config_hash,
            "protocol_key": PHASE9_PROTOCOL,
            "split_method": PHASE9_SPLIT_METHOD,
            "settings": {
                "validation_history_hours": settings.validation_history_hours,
                "validation_target_hours": settings.validation_target_hours,
                "validation_max_folds": settings.validation_max_folds,
                "validation_top_k": settings.validation_top_k,
                "validation_resolution": settings.validation_resolution,
            },
        }
        methods = base.get("methods", {})
        risk = methods.get("civicflow_risk", {})
        candidates = {
            key: value
            for key, value in methods.items()
            if key.startswith("baseline_") and value.get("pr_auc") is not None
        }
        best_name, best = (
            max(candidates.items(), key=lambda item: item[1]["pr_auc"])
            if candidates
            else ("none", {})
        )
        _persist(
            session,
            dataset,
            experiment_type=experiment_type,
            variant_key=FULL_VARIANT,
            name=f"Phase 9 full-model {experiment_type.value.lower()} · {dataset.dataset_key}",
            method="rolling-origin temporal holdout on next-period activity",
            metrics=base,
            baselines={
                key: value for key, value in methods.items() if key != "civicflow_risk"
            },
            findings=[
                f"Dataset {dataset.dataset_key} has {len(records)} normalized records.",
                f"CivicFlow mean PR-AUC {risk.get('pr_auc')} and ROC-AUC {risk.get('roc_auc')}.",
                f"Strongest baseline {best_name} PR-AUC {best.get('pr_auc')}.",
                "Metrics use the same rolling origins, labels, and top-k for all methods.",
            ],
            limitations=[
                "Target is next-window 311 activity, not verified municipal impact.",
                "Category and severity mappings are explicit heuristics.",
                "Rolling origins overlap in time and are not independent samples.",
                "Infrastructure and dependency metadata are absent from the isolated validation database.",
            ],
            reproducibility=reproducibility,
            actor_id=actor_id,
            config=config,
        )
        diagnostic = run_diagnostic_audit(
            records,
            settings=settings,
            config=config,
            dataset_key=dataset.dataset_key,
            bbox=bbox,
            base_result=base,
        )
        diagnostic["record_count"] = len(records)
        _persist(
            session,
            dataset,
            experiment_type=ValidationExperimentType.RISK_DIAGNOSTIC,
            variant_key=DIAGNOSTIC_VARIANT,
            name=f"Phase 9 diagnostic audit · {dataset.dataset_key}",
            method="factor availability, associations, redundancy, score and band diagnostics",
            metrics=diagnostic,
            baselines=diagnostic.get("baseline_comparison", {}),
            findings=[item["finding"] for item in diagnostic.get("hypotheses", [])],
            limitations=diagnostic.get("limitations", []),
            reproducibility=reproducibility,
            actor_id=actor_id,
            config=config,
        )
        ablation = run_ablation_suite(
            records,
            settings=settings,
            config=config,
            dataset_key=dataset.dataset_key,
            bbox=bbox,
            base_result=base,
        )
        ablation["record_count"] = len(records)
        _persist(
            session,
            dataset,
            experiment_type=ValidationExperimentType.RISK_ABLATION,
            variant_key=ABLATION_VARIANT,
            name=f"Phase 9 factor ablation · {dataset.dataset_key}",
            method="leave-one-out and single-factor variants on identical folds",
            metrics=ablation,
            baselines=methods,
            findings=[
                f"Best variant: {ablation.get('best_variant')}; "
                f"best-minus-full PR-AUC: {ablation.get('best_minus_full_pr_auc')}.",
                ablation.get("interpretation", ""),
            ],
            limitations=ablation.get("limitations", []),
            reproducibility=reproducibility,
            actor_id=actor_id,
            config=config,
        )
        robustness = run_robustness_suite(
            records,
            settings=settings,
            config=config,
            dataset_key=dataset.dataset_key,
            bbox=bbox,
            base_result=base,
        )
        robustness["record_count"] = len(records)
        _persist(
            session,
            dataset,
            experiment_type=ValidationExperimentType.RISK_ROBUSTNESS,
            variant_key=ROBUSTNESS_VARIANT,
            name=f"Phase 9 robustness suite · {dataset.dataset_key}",
            method="resolution, window, density, thresholds, thinning, ranking stability",
            metrics=robustness,
            baselines={"base": robustness.get("base_metrics", {})},
            findings=[
                "Resolution variants: "
                + ", ".join(
                    f"H3-{row['resolution']} PR-AUC {row['metrics'].get('pr_auc')}"
                    for row in robustness.get("resolution", [])
                ),
                "Window variants: "
                + ", ".join(
                    f"{row['target_hours']}h PR-AUC {row['metrics'].get('pr_auc')}"
                    for row in robustness.get("target_window", [])
                ),
                "Dense stratum PR-AUC "
                f"{robustness.get('density_strata', {}).get('dense', {}).get('pr_auc')}; "
                "sparse stratum PR-AUC "
                f"{robustness.get('density_strata', {}).get('sparse', {}).get('pr_auc')}.",
            ],
            limitations=robustness.get("limitations", []),
            reproducibility=reproducibility,
            actor_id=actor_id,
            config=config,
        )
        if dataset.dataset_key == PHASE9_DEVELOPMENT_DATASET:
            selection = _select_candidate(ablation, dataset.dataset_key)
        if selection and selection.get("candidate_key"):
            sample = (
                "selection"
                if dataset.dataset_key == selection["selection_dataset"]
                else "external_holdout"
            )
            candidate = _evaluate_candidate(
                records=records,
                settings=settings,
                config=config,
                selection=selection,
                dataset_key=dataset.dataset_key,
                bbox=bbox,
                base=base,
                sample=sample,
            )
            candidate["record_count"] = len(records)
            _persist(
                session,
                dataset,
                experiment_type=ValidationExperimentType.RISK_ABLATION,
                variant_key=f"candidate_{selection['candidate_key']}",
                name=(f"Phase 9 candidate {selection['candidate_key']} · {dataset.dataset_key}"),
                method="evaluation-only candidate compared on identical folds",
                metrics=candidate,
                baselines={"reference_civicflow": candidate.get("reference_metrics", {})},
                findings=[
                    f"Candidate {selection['candidate_key']} sample={sample}.",
                    f"Mean paired PR-AUC delta {(candidate.get('delta_pr_auc') or {}).get('mean_delta')}.",
                    "No model was activated by this evaluation.",
                ],
                limitations=candidate.get("limitations", []),
                reproducibility=reproducibility,
                actor_id=actor_id,
                config=config,
            )
    summary = _summarize(session, datasets)
    summary["runtime_ms"] = round((time.perf_counter() - started) * 1000, 1)
    summary["selection"] = selection
    summary["note"] = (
        "Dataset-level results are descriptive. No model was activated by this run."
    )
    return summary


def _selection_from_session(session: Session) -> dict | None:
    """Reuse the persisted development-dataset selection when it exists."""
    dataset = session.scalar(
        select(ValidationDataset).where(
            ValidationDataset.dataset_key == PHASE9_DEVELOPMENT_DATASET
        )
    )
    if dataset is None:
        return None
    experiment = session.scalar(
        select(ValidationExperiment)
        .where(
            ValidationExperiment.dataset_id == dataset.id,
            ValidationExperiment.protocol_key == PHASE9_PROTOCOL,
            ValidationExperiment.experiment_type == ValidationExperimentType.RISK_ABLATION,
            ValidationExperiment.variant_key == ABLATION_VARIANT,
        )
        .order_by(ValidationExperiment.created_at.desc())
        .limit(1)
    )
    if experiment is None:
        return None
    return _select_candidate(experiment.metrics or {}, dataset.dataset_key)


def _experiments_by_type(
    session: Session, datasets: list[ValidationDataset]
) -> dict[str, dict[tuple[str, str], ValidationExperiment]]:
    if not datasets:
        return {}
    # Append-only runs accumulate rows whose metrics payloads are large. Read a
    # bounded newest-first window and keep the first row seen per key so a GET
    # cannot be made arbitrarily expensive by repeated runs.
    rows = session.scalars(
        select(ValidationExperiment)
        .where(
            ValidationExperiment.protocol_key == PHASE9_PROTOCOL,
            ValidationExperiment.dataset_id.in_([item.id for item in datasets]),
        )
        .order_by(ValidationExperiment.created_at.desc())
        .limit(PHASE9_EXPERIMENT_READ_LIMIT)
    ).all()
    latest: dict[str, dict[tuple[str, str], ValidationExperiment]] = {}
    for row in rows:
        latest.setdefault(str(row.dataset_id), {}).setdefault(
            (row.experiment_type.value, row.variant_key or ""), row
        )
    return latest


def _baseline_rows(methods: dict, statistics_block: dict) -> list[dict]:
    paired = statistics_block.get("paired_pr_auc_vs_baselines") or {}
    rows = []
    for method, metrics in methods.items():
        if not method.startswith("baseline_"):
            continue
        delta = paired.get(method) or {}
        rows.append(
            {
                "method": method,
                "pr_auc": metrics.get("pr_auc"),
                "roc_auc": metrics.get("roc_auc"),
                "precision_at_k": metrics.get("precision_at_k"),
                "recall_at_k": metrics.get("recall_at_k"),
                "delta_pr_auc": delta.get("mean_delta"),
                "ci_low": delta.get("ci_low"),
                "ci_high": delta.get("ci_high"),
                "wins": delta.get("wins"),
                "losses": delta.get("losses"),
                "sign_test_p": delta.get("sign_test_p"),
            }
        )
    rows.sort(key=lambda item: item["pr_auc"] or -1, reverse=True)
    return rows


def _ablation_view(metrics: dict) -> dict:
    variants = []
    for item in metrics.get("variants") or []:
        delta = item.get("delta_pr_auc") or {}
        variants.append(
            {
                "variant_key": item.get("variant_key"),
                "kind": item.get("kind"),
                "removed_factors": item.get("removed_factors") or [],
                "only_factors": item.get("only_factors") or [],
                "pr_auc": (item.get("metrics") or {}).get("pr_auc"),
                "roc_auc": (item.get("metrics") or {}).get("roc_auc"),
                "precision_at_k": (item.get("metrics") or {}).get("precision_at_k"),
                "recall_at_k": (item.get("metrics") or {}).get("recall_at_k"),
                "mean_delta": delta.get("mean_delta"),
                "ci_low": delta.get("ci_low"),
                "ci_high": delta.get("ci_high"),
                "wins": delta.get("wins"),
                "losses": delta.get("losses"),
                "sign_test_p": delta.get("sign_test_p"),
            }
        )
    return {
        "status": metrics.get("status"),
        "variants": variants,
        "ranking": (metrics.get("ranking") or [])[:12],
        "best_variant": metrics.get("best_variant"),
        "best_minus_full_pr_auc": metrics.get("best_minus_full_pr_auc"),
        "interpretation": metrics.get("interpretation"),
        "limitations": metrics.get("limitations") or [],
    }


def _robustness_view(metrics: dict) -> dict:
    def rows(items, key):
        result = []
        for item in items or []:
            stability = item.get("stability_vs_default") or {}
            result.append(
                {
                    key: item.get(key),
                    "pr_auc": (item.get("metrics") or {}).get("pr_auc"),
                    "roc_auc": (item.get("metrics") or {}).get("roc_auc"),
                    "precision_at_k": (item.get("metrics") or {}).get("precision_at_k"),
                    "recall_at_k": (item.get("metrics") or {}).get("recall_at_k"),
                    "cell_count": item.get("cell_count"),
                    "retained_records": item.get("retained_records"),
                    "mean_spearman": stability.get("mean_spearman"),
                    "mean_top20_jaccard": stability.get("mean_top20_jaccard"),
                }
            )
        return result

    return {
        "status": metrics.get("status"),
        "base_metrics": metrics.get("base_metrics") or {},
        "resolution": rows(metrics.get("resolution"), "resolution"),
        "target_window": rows(metrics.get("target_window"), "target_hours"),
        "record_thinning": rows(metrics.get("record_thinning"), "retained_fraction"),
        "density_strata": metrics.get("density_strata") or {},
        "threshold_sensitivity": metrics.get("threshold_sensitivity") or {},
        "missingness": metrics.get("missingness") or {},
        "runtime_ms": metrics.get("runtime_ms"),
        "limitations": metrics.get("limitations") or [],
    }


def _curate_dataset(
    dataset: ValidationDataset,
    experiments: dict[tuple[str, str], ValidationExperiment],
) -> dict:
    full = None
    for experiment_type in CORE_TYPES:
        full = experiments.get((experiment_type.value, FULL_VARIANT))
        if full is not None:
            break
    metrics = (full.metrics if full else {}) or {}
    methods = metrics.get("methods") or {}
    risk = methods.get("civicflow_risk") or {}
    statistics_block = metrics.get("statistics") or {}
    baselines = _baseline_rows(methods, statistics_block)
    best_baseline = baselines[0] if baselines else None
    diagnostic = experiments.get(
        (ValidationExperimentType.RISK_DIAGNOSTIC.value, DIAGNOSTIC_VARIANT)
    )
    diag_metrics = (diagnostic.metrics if diagnostic else {}) or {}
    ablation = experiments.get(
        (ValidationExperimentType.RISK_ABLATION.value, ABLATION_VARIANT)
    )
    robustness = experiments.get(
        (ValidationExperimentType.RISK_ROBUSTNESS.value, ROBUSTNESS_VARIANT)
    )
    candidate_rows = []
    for (experiment_type, variant_key), experiment in experiments.items():
        if experiment_type != ValidationExperimentType.RISK_ABLATION.value:
            continue
        if not variant_key.startswith("candidate_"):
            continue
        if experiment.status != ValidationStatus.COMPLETED:
            continue
        candidate_metrics = experiment.metrics or {}
        candidate_rows.append(
            {
                "experiment_id": str(experiment.id),
                "variant_key": variant_key,
                "sample": candidate_metrics.get("sample"),
                "candidate_key": candidate_metrics.get("candidate_key"),
                "removed_factors": candidate_metrics.get("removed_factors") or [],
                "metrics": candidate_metrics.get("metrics") or {},
                "reference_metrics": candidate_metrics.get("reference_metrics") or {},
                "delta_pr_auc": candidate_metrics.get("delta_pr_auc") or {},
                "delta_roc_auc": candidate_metrics.get("delta_roc_auc") or {},
                "activated": bool(candidate_metrics.get("activated")),
                "limitations": candidate_metrics.get("limitations") or [],
            }
        )
    limitations = []
    for experiment in experiments.values():
        for item in experiment.limitations or []:
            if item not in limitations:
                limitations.append(item)
    findings = []
    if full is not None:
        findings.extend(full.findings or [])
    return {
        "dataset_id": str(dataset.id),
        "dataset_key": dataset.dataset_key,
        "name": dataset.name,
        "region": dataset.region,
        "period_start": dataset.period_start.isoformat() if dataset.period_start else None,
        "period_end": dataset.period_end.isoformat() if dataset.period_end else None,
        "record_count": dataset.record_count,
        "snapshot_sha256": dataset.snapshot_sha256,
        "schema_version": dataset.schema_version,
        "status": full.status.value if full else "INSUFFICIENT_DATA",
        "evidence_kind": (
            full.evidence_kind.value if full else PHASE9_EVIDENCE_KIND.value
        ),
        "model_version": full.model_version if full else None,
        "config_hash": full.config_hash if full else None,
        "split_method": full.split_method if full else PHASE9_SPLIT_METHOD,
        "role": (
            "development"
            if dataset.dataset_key == PHASE9_DEVELOPMENT_DATASET
            else "external"
        ),
        "risk": {
            "pr_auc": risk.get("pr_auc"),
            "roc_auc": risk.get("roc_auc"),
            "precision_at_k": risk.get("precision_at_k"),
            "recall_at_k": risk.get("recall_at_k"),
            "fold_count": risk.get("fold_count"),
        },
        "baselines": baselines,
        "best_baseline": best_baseline,
        "statistics": statistics_block,
        "density": metrics.get("density") or {},
        "sensitivity": metrics.get("sensitivity") or {},
        "diagnostics": {
            "hypotheses": diag_metrics.get("hypotheses") or [],
            "factor_diagnostics": diag_metrics.get("factor_diagnostics") or {},
            "factor_redundancy": (diag_metrics.get("factor_redundancy") or [])[:8],
            "band_distribution": diag_metrics.get("band_distribution") or {},
            "score_distribution": diag_metrics.get("score_distribution") or {},
            "data_quality": diag_metrics.get("data_quality") or {},
            "baseline_comparison": diag_metrics.get("baseline_comparison") or {},
            "limitations": diagnostic.limitations if diagnostic else [],
        },
        "ablation": _ablation_view((ablation.metrics if ablation else {}) or {}),
        "candidates": candidate_rows,
        "robustness": _robustness_view((robustness.metrics if robustness else {}) or {}),
        "findings": findings,
        "limitations": limitations,
        "experiments": {
            f"{experiment_type}:{variant_key}": {
                "id": str(experiment.id),
                "name": experiment.name,
                "status": experiment.status.value,
                "completed_at": experiment.completed_at.isoformat()
                if experiment.completed_at
                else None,
            }
            for (experiment_type, variant_key), experiment in experiments.items()
        },
    }


def _summarize(session: Session, datasets: list[ValidationDataset]) -> dict:
    experiments = _experiments_by_type(session, datasets)
    curated = [
        _curate_dataset(dataset, experiments.get(str(dataset.id), {}))
        for dataset in datasets
        if experiments.get(str(dataset.id))
    ]
    curated.sort(key=lambda item: (item["role"] != "development", item["dataset_key"]))
    values = [
        item["risk"]["pr_auc"]
        for item in curated
        if item["risk"].get("pr_auc") is not None
    ]
    return {
        "protocol_key": PHASE9_PROTOCOL,
        "protocol": PHASE9_METHOD,
        "split_method": PHASE9_SPLIT_METHOD,
        "development_dataset": PHASE9_DEVELOPMENT_DATASET,
        "dataset_count": len(curated),
        "mean_pr_auc_across_datasets": _round(statistics.fmean(values)) if values else None,
        "evidence_kind": PHASE9_EVIDENCE_KIND.value,
        "evidence_policy": [
            "Results are EMPIRICAL_OBSERVATIONAL over public NYC 311 complaint snapshots.",
            "The target is next-window complaint activity, not verified municipal impact.",
            "Phase 8 synthetic correlation and simulated planning evidence stays separately labelled.",
            "No risk configuration was activated by this research protocol.",
        ],
        "datasets": curated,
    }


def phase9_summary(session: Session) -> dict:
    """Read persisted Phase 9 experiments without recomputing anything."""
    datasets = list(
        session.scalars(
            select(ValidationDataset).order_by(ValidationDataset.created_at)
        ).all()
    )
    experiments = _experiments_by_type(session, datasets)
    researched = [item for item in datasets if experiments.get(str(item.id))]
    summary = _summarize(session, researched)
    summary["selection"] = _selection_from_session(session) or _select_candidate(
        {}, PHASE9_DEVELOPMENT_DATASET
    )
    return summary
