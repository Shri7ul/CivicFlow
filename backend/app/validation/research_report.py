"""Phase 9 research report generated from persisted validation experiments.

The report is a deterministic projection of stored experiment rows. It never
invents metrics, never recomputes a backtest, and never claims a capability the
stored evidence does not support.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ValidationDataset, ValidationExperiment, ValidationExperimentType
from app.validation.research import (
    PHASE9_DEVELOPMENT_DATASET,
    PHASE9_METHOD,
    PHASE9_PROTOCOL,
    PHASE9_SPLIT_METHOD,
    phase9_summary,
)


def _number(value, digits: int = 6) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def _phase8_baseline(session: Session) -> dict | None:
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
            ValidationExperiment.protocol_key.is_(None),
            ValidationExperiment.experiment_type == ValidationExperimentType.RISK_BACKTEST,
        )
        .order_by(ValidationExperiment.created_at.desc())
        .limit(1)
    )
    if experiment is None:
        return None
    metrics = experiment.metrics or {}
    methods = metrics.get("methods") or {}
    risk = methods.get("civicflow_risk") or {}
    baselines = {
        key: value
        for key, value in methods.items()
        if key.startswith("baseline_")
    }
    ranked = sorted(
        (
            (key, value)
            for key, value in baselines.items()
            if value.get("pr_auc") is not None
        ),
        key=lambda item: item[1]["pr_auc"],
        reverse=True,
    )
    best_name, best = ranked[0] if ranked else ("none", {})
    delta = None
    if risk.get("pr_auc") is not None and best.get("pr_auc") is not None:
        delta = round(float(best["pr_auc"]) - float(risk["pr_auc"]), 6)
    return {
        "experiment_id": str(experiment.id),
        "dataset_key": dataset.dataset_key,
        "snapshot_sha256": dataset.snapshot_sha256,
        "risk_pr_auc": risk.get("pr_auc"),
        "risk_roc_auc": risk.get("roc_auc"),
        "best_baseline": best_name,
        "best_baseline_pr_auc": best.get("pr_auc"),
        "baseline_minus_risk_pr_auc": delta,
        "findings": experiment.findings or [],
        "limitations": experiment.limitations or [],
        "methods": {
            key: {
                "pr_auc": value.get("pr_auc"),
                "roc_auc": value.get("roc_auc"),
                "precision_at_k": value.get("precision_at_k"),
                "recall_at_k": value.get("recall_at_k"),
            }
            for key, value in methods.items()
        },
    }


def _executive_summary(datasets: list[dict], selection: dict | None) -> list[str]:
    if not datasets:
        return ["No Phase 9 experiment records are persisted, so no finding is reported."]
    lines: list[str] = []
    model_version = datasets[0].get("model_version") or "unknown"
    lines.append(
        f"{len(datasets)} public NYC 311 snapshots were evaluated with the registered "
        f"{model_version} risk model under {PHASE9_PROTOCOL}."
    )
    for item in datasets:
        risk = item["risk"]
        best = item["best_baseline"]
        if risk.get("pr_auc") is None:
            lines.append(
                f"{item['dataset_key']} ({item['role']}): insufficient evidence; no "
                "ranking metric was produced."
            )
            continue
        if best and best.get("pr_auc") is not None:
            delta = float(risk["pr_auc"]) - float(best["pr_auc"])
            direction = "above" if delta > 0 else "below"
            lines.append(
                f"{item['dataset_key']} ({item['role']}, {item['record_count']} records): "
                f"CivicFlow PR-AUC {_number(risk['pr_auc'])} is {_number(abs(delta))} "
                f"{direction} the strongest baseline ({best['method']}, "
                f"{_number(best['pr_auc'])})."
            )
        else:
            lines.append(
                f"{item['dataset_key']} ({item['role']}): CivicFlow PR-AUC "
                f"{_number(risk['pr_auc'])}; no baseline metric is available."
            )
    beats = [
        item
        for item in datasets
        if item["risk"].get("pr_auc") is not None
        and item["best_baseline"]
        and item["best_baseline"].get("pr_auc") is not None
        and item["risk"]["pr_auc"] > item["best_baseline"]["pr_auc"]
    ]
    lines.append(
        f"CivicFlow ranks above every baseline on {len(beats)} of {len(datasets)} datasets."
    )
    significant = []
    improving = []
    for item in datasets:
        for variant in item["ablation"]["variants"]:
            if variant.get("kind") != "leave_one_out":
                continue
            if variant.get("ci_low") is not None and variant["ci_low"] > 0:
                significant.append((item["dataset_key"], variant["variant_key"]))
            if variant.get("mean_delta") is not None and variant["mean_delta"] > 0:
                improving.append((item["dataset_key"], variant["variant_key"]))
    lines.append(
        f"{len(improving)} leave-one-out variants had a positive mean paired PR-AUC "
        f"delta; {len(significant)} had a bootstrap interval that excluded zero."
    )
    if selection and selection.get("candidate_key"):
        lines.append(
            f"The pre-registered selection rule chose {selection['candidate_key']} on "
            f"{selection['selection_dataset']}; external results are reported as holdout "
            "evidence only."
        )
    else:
        lines.append(
            "The pre-registered selection rule produced no candidate because no "
            "leave-one-out variant improved the development dataset."
        )
    lines.append(
        "All results are descriptive ranking evidence over complaint activity; no "
        "model configuration was activated and no predictive or causal claim is made."
    )
    return lines


def _model_changes(datasets: list[dict], selection: dict | None) -> dict:
    candidates = [row for item in datasets for row in item["candidates"]]
    holdout = [row for row in candidates if row.get("sample") == "external_holdout"]
    better = [
        row
        for row in holdout
        if (row["delta_pr_auc"].get("ci_low") or -1) > 0
    ]
    if not (selection or {}).get("candidate_key"):
        decision = (
            "No model change was proposed: the pre-registered selection rule found no "
            "leave-one-out variant with a positive mean paired PR-AUC delta on the "
            "development dataset."
        )
    elif not candidates:
        decision = (
            f"The pre-registered rule selected {(selection or {}).get('candidate_key')} on "
            f"{(selection or {}).get('selection_dataset')}, but no candidate evaluation is "
            "persisted yet, so the change is unproven and the registered model is retained."
        )
    elif not holdout:
        decision = (
            "A candidate was selected but no external holdout dataset was evaluated, "
            "so the change remains unproven."
        )
    elif better and len(better) == len(holdout):
        decision = (
            f"All {len(holdout)} external holdouts showed a bootstrap interval above "
            "zero for the candidate. Activation would still require governed model "
            "registration, a fresh evaluation, and explicit approval outside this "
            "research protocol; nothing was activated here."
        )
    elif better:
        decision = (
            f"{len(better)} of {len(holdout)} external holdouts showed a bootstrap "
            "interval above zero for the candidate, so the improvement is not "
            "consistent across regions or periods. The candidate is reported as "
            "mixed evidence and is not proposed for activation; the registered "
            "model is retained unchanged."
        )
    else:
        decision = (
            f"0 of {len(holdout)} external holdouts showed a bootstrap interval above "
            "zero for the candidate. The registered model is retained unchanged."
        )
    return {
        "activated": False,
        "activation_state": "NOT_ACTIVATED",
        "active_model_version": datasets[0].get("model_version") if datasets else None,
        "active_config_hash": datasets[0].get("config_hash") if datasets else None,
        "selection_rule": (selection or {}).get("rule"),
        "selected_candidate": (selection or {}).get("candidate_key"),
        "selection_dataset": (selection or {}).get("selection_dataset"),
        "selection_reason": (selection or {}).get("reason"),
        "candidate_rows": candidates,
        "decision": decision,
        "governance_note": (
            "Model activation remains an explicit ADMIN operation on the existing "
            "model registry; this report cannot change the active configuration."
        ),
    }


def _comparison_rows(datasets: list[dict]) -> list[dict]:
    rows = []
    for item in datasets:
        risk = item["risk"]
        best = item["best_baseline"] or {}
        delta = None
        if risk.get("pr_auc") is not None and best.get("pr_auc") is not None:
            delta = round(float(risk["pr_auc"]) - float(best["pr_auc"]), 6)
        rows.append(
            {
                "dataset_key": item["dataset_key"],
                "role": item["role"],
                "region": item["region"],
                "period_start": item["period_start"],
                "period_end": item["period_end"],
                "record_count": item["record_count"],
                "civicflow_pr_auc": risk.get("pr_auc"),
                "civicflow_roc_auc": risk.get("roc_auc"),
                "best_baseline": best.get("method"),
                "best_baseline_pr_auc": best.get("pr_auc"),
                "pr_auc_delta_vs_best_baseline": delta,
                "density_classification": (item["density"] or {}).get(
                    "classification"
                ),
                "factor_count": len(
                    [
                        key
                        for key, value in (item["diagnostics"]["factor_diagnostics"] or {}).items()
                        if (value or {}).get("available_count")
                    ]
                ),
            }
        )
    return rows


def _future_research(datasets: list[dict], summary: dict) -> list[str]:
    ideas: list[str] = []
    unavailable = set()
    dense = []
    for item in datasets:
        for key, value in (item["diagnostics"]["factor_diagnostics"] or {}).items():
            if not (value or {}).get("available_count"):
                unavailable.add(key)
        if (item["density"] or {}).get("classification") == "DENSE":
            dense.append(item["dataset_key"])
    if unavailable:
        unavailable_text = ", ".join(sorted(unavailable))
        ideas.append(
            "Populate the validation database with infrastructure and dependency "
            f"metadata so {unavailable_text} can be tested; their configured "
            "weight is currently excluded and renormalized."
        )
    ideas.append(
        "Acquire verified municipal outcome, hazard, or field-inspection ground truth; "
        "complaint activity measures reporting behaviour as well as urban conditions."
    )
    if dense:
        ideas.append(
            "Replicate on genuinely sparse geographies and longer periods; the evaluated "
            f"target is dense on {len(dense)} of {len(datasets)} datasets, which favours "
            "persistence-style baselines."
        )
    ideas.append(
        "Extend the protocol with an explicit spatial holdout (held-out borough) to "
        "measure cross-geography transfer instead of same-area temporal ranking."
    )
    ideas.append(
        "Increase the number of non-overlapping evaluation origins or use a blocked "
        "temporal design so paired comparisons carry more independent information."
    )
    if summary.get("mean_pr_auc_across_datasets") is None:
        ideas.append("Register at least one dataset that yields completed folds.")
    return ideas


def build_research_report(session: Session) -> dict:
    """Render the Phase 9 report strictly from persisted experiment records."""
    summary = phase9_summary(session)
    datasets = summary["datasets"]
    selection = summary.get("selection")
    dataset_rows = []
    for item in datasets:
        record = session.get(ValidationDataset, item["dataset_id"])
        reproducibility = {}
        if record is not None:
            reproducibility = {
                "source_url": record.source_url,
                "license_note": record.license_note,
                "metadata": record.dataset_metadata or {},
            }
        dataset_rows.append(
            {
                "dataset_key": item["dataset_key"],
                "name": item["name"],
                "region": item["region"],
                "period_start": item["period_start"],
                "period_end": item["period_end"],
                "record_count": item["record_count"],
                "snapshot_sha256": item["snapshot_sha256"],
                "schema_version": item["schema_version"],
                "role": item["role"],
                "source_url": reproducibility.get("source_url"),
                "license_note": reproducibility.get("license_note"),
                "bbox": (
                    (reproducibility.get("metadata") or {}).get("bbox")
                    or ((reproducibility.get("metadata") or {}).get("query") or {}).get(
                        "bbox"
                    )
                ),
                "evidence_kind": item["evidence_kind"],
            }
        )
    limitations: list[str] = []
    for item in datasets:
        for text in item["limitations"]:
            if text not in limitations:
                limitations.append(text)
    protocol_limitations = [
        "Complaint activity is a proxy for urban conditions, not verified hazard impact.",
        "Rolling origins overlap in time; bootstrap intervals describe variability "
        "across observed origins, not population-level confidence.",
        "H3 cells and days are repeated observations and are not independent samples.",
        "No external municipal action, dispatch, or incident mutation was performed.",
    ]
    for text in protocol_limitations:
        if text not in limitations:
            limitations.append(text)
    return {
        "protocol_key": PHASE9_PROTOCOL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "persisted validation_experiments rows",
        "evidence_kind": summary["evidence_kind"],
        "executive_summary": _executive_summary(datasets, selection),
        "phase8_findings": _phase8_baseline(session),
        "diagnostic_audit": [
            {
                "dataset_key": item["dataset_key"],
                "role": item["role"],
                "hypotheses": item["diagnostics"]["hypotheses"],
                "factor_diagnostics": item["diagnostics"]["factor_diagnostics"],
                "factor_redundancy": item["diagnostics"]["factor_redundancy"],
                "band_distribution": item["diagnostics"]["band_distribution"],
                "score_distribution": item["diagnostics"]["score_distribution"],
            }
            for item in datasets
        ],
        "datasets": dataset_rows,
        "dataset_quality": [
            {
                "dataset_key": item["dataset_key"],
                "data_quality": item["diagnostics"]["data_quality"],
                "density": item["density"],
                "missingness": item["robustness"]["missingness"],
            }
            for item in datasets
        ],
        "methodology": {
            "protocol": PHASE9_METHOD,
            "model_name": "risk",
            "model_version": datasets[0].get("model_version") if datasets else None,
            "config_hash": datasets[0].get("config_hash") if datasets else None,
            "metrics": [
                "pr_auc",
                "roc_auc",
                "precision_at_k",
                "recall_at_k",
            ],
            "target": "next-window H3 activity label (any record)",
            "statistical_unit": "rolling-origin fold",
            "notes": [
                "Each fold fits no parameters; the risk engine is a deterministic "
                "heuristic scoring function.",
                "Baselines are computed on the same folds, labels, and top-k.",
                "Threshold sensitivity changes band labels only, never the ranking.",
            ],
        },
        "split_methodology": {
            "method": PHASE9_SPLIT_METHOD,
            "description": (
                "Every fold uses history strictly before the origin and a disjoint "
                "future window as the target; no future record enters a score."
            ),
            "leakage_controls": [
                "History and target windows never overlap.",
                "Thresholds and resolutions are reported as sensitivity, not tuned.",
                "Candidate selection uses only the development dataset.",
                "External datasets are never used for selection or tuning.",
                "Evaluation uses an isolated SQLite snapshot with no operational rows.",
            ],
            "unavailable": [
                "A strict spatial holdout (held-out borough training transfer) is not "
                "implemented because the engine fits no parameters; cross-region "
                "results are reported as separate evaluations.",
                "Non-overlapping origins are limited by the snapshot length.",
            ],
        },
        "baselines": [
            {"dataset_key": item["dataset_key"], "rows": item["baselines"]}
            for item in datasets
        ],
        "ablation": [
            {"dataset_key": item["dataset_key"], **item["ablation"]}
            for item in datasets
        ],
        "geographic": [
            row for row in _comparison_rows(datasets) if row["role"] == "external"
        ],
        "temporal": [
            {
                "dataset_key": item["dataset_key"],
                "period_start": item["period_start"],
                "period_end": item["period_end"],
                "pr_auc": item["risk"].get("pr_auc"),
                "roc_auc": item["risk"].get("roc_auc"),
                "density": (item["density"] or {}).get("classification"),
                "fold_count": item["risk"].get("fold_count"),
            }
            for item in datasets
            if "2025q2" in item["dataset_key"] or "2025q1" in item["dataset_key"]
        ],
        "sensitivity": [
            {
                "dataset_key": item["dataset_key"],
                "resolution": item["robustness"]["resolution"],
                "target_window": item["robustness"]["target_window"],
                "record_thinning": item["robustness"]["record_thinning"],
                "density_strata": item["robustness"]["density_strata"],
                "threshold_sensitivity": item["robustness"]["threshold_sensitivity"],
                "missingness": item["robustness"]["missingness"],
            }
            for item in datasets
        ],
        "statistics": [
            {
                "dataset_key": item["dataset_key"],
                "fold_intervals": item["statistics"].get("fold_intervals"),
                "paired_pr_auc_vs_baselines": item["statistics"].get(
                    "paired_pr_auc_vs_baselines"
                ),
                "method": item["statistics"].get("method"),
            }
            for item in datasets
        ],
        "model_changes": _model_changes(datasets, selection),
        "comparison": _comparison_rows(datasets),
        "limitations": limitations,
        "reproducibility": {
            "protocol_key": PHASE9_PROTOCOL,
            "split_method": PHASE9_SPLIT_METHOD,
            "mean_pr_auc_across_datasets": summary.get(
                "mean_pr_auc_across_datasets"
            ),
            "bootstrap_seed": 20261124,
            "bootstrap_resamples": 2000,
            "datasets": [
                {
                    "dataset_key": item["dataset_key"],
                    "snapshot_sha256": item["snapshot_sha256"],
                    "record_count": item["record_count"],
                    "config_hash": item["config_hash"],
                    "model_version": item["model_version"],
                    "experiments": item["experiments"],
                }
                for item in datasets
            ],
            "commands": [
                ".venv/Scripts/python.exe scripts/run_phase9_research.py",
                ".venv/Scripts/python.exe scripts/generate_phase9_report.py --output docs/phase9-report.json",
            ],
        },
        "future_research": _future_research(datasets, summary),
        "dataset_count": summary["dataset_count"],
    }
