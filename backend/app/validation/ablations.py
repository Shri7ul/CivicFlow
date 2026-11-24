"""Leakage-safe factor ablation for the existing risk model."""

from __future__ import annotations

import time
from dataclasses import replace

from app.core.config import Settings
from app.risk.config import FACTOR_KEYS, RiskConfig
from app.validation.risk import run_risk_backtest
from app.validation.stats import paired_comparison


def _normalized(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Ablation variant must retain at least one factor.")
    return {key: round(value / total, 10) for key, value in weights.items()}


def ablation_variants(base: RiskConfig) -> list[dict]:
    variants = [{"key": "full", "kind": "full", "removed": [], "only": []}]
    for key in FACTOR_KEYS:
        variants.append(
            {
                "key": f"drop_{key}",
                "kind": "leave_one_out",
                "removed": [key],
                "only": [],
            }
        )
        variants.append(
            {
                "key": f"only_{key}",
                "kind": "single_factor",
                "removed": [],
                "only": [key],
            }
        )
    return variants


def variant_config(base: RiskConfig, variant: dict, suffix: str) -> RiskConfig:
    weights = dict(base.weights)
    if variant["only"]:
        weights = {key: (1.0 if key in variant["only"] else 0.0) for key in FACTOR_KEYS}
    else:
        for key in variant["removed"]:
            weights[key] = 0.0
    return replace(
        base,
        weights=_normalized(weights),
        model_version=f"{base.model_version}-{suffix}",
    )


def _fold_metric(result: dict, metric: str) -> list[float]:
    values = []
    for fold in result.get("folds", []):
        value = ((fold.get("metrics") or {}).get("civicflow_risk") or {}).get(metric)
        if value is not None:
            values.append(float(value))
    return values


def run_ablation_suite(
    records: list[dict],
    *,
    settings: Settings,
    config: RiskConfig,
    dataset_key: str,
    bbox: tuple[float, float, float, float],
    base_result: dict | None = None,
) -> dict:
    started = time.perf_counter()
    base = base_result or run_risk_backtest(
        records,
        settings=settings,
        config=config,
        dataset_key=dataset_key,
        bbox=bbox,
        include_sensitivity=False,
    )
    base_fold_pr = _fold_metric(base, "pr_auc")
    base_fold_roc = _fold_metric(base, "roc_auc")
    variants = []
    for variant in ablation_variants(config):
        if variant["key"] == "full":
            result = base
        else:
            candidate = variant_config(config, variant, variant["key"])
            result = run_risk_backtest(
                records,
                settings=settings,
                config=candidate,
                dataset_key=dataset_key,
                bbox=bbox,
                include_sensitivity=False,
            )
        metrics = (result.get("methods") or {}).get("civicflow_risk", {})
        fold_pr = _fold_metric(result, "pr_auc")
        delta_pr = [
            round(candidate - reference, 6)
            for candidate, reference in zip(fold_pr, base_fold_pr)
        ]
        delta_roc = [
            round(candidate - reference, 6)
            for candidate, reference in zip(
                _fold_metric(result, "roc_auc"), base_fold_roc
            )
        ]
        variants.append(
            {
                "variant_key": variant["key"],
                "kind": variant["kind"],
                "removed_factors": variant["removed"],
                "only_factors": variant["only"],
                "weights": dict(result.get("risk_config", {}).get("weights", {})),
                "config_hash": result.get("config_hash"),
                "status": result.get("status"),
                "fold_count": len(result.get("folds", [])),
                "metrics": metrics,
                "delta_pr_auc": paired_comparison(delta_pr),
                "delta_roc_auc": paired_comparison(delta_roc),
            }
        )
    completed = [item for item in variants if item["metrics"].get("pr_auc") is not None]
    ranked = sorted(completed, key=lambda item: item["metrics"]["pr_auc"], reverse=True)
    full = next((item for item in variants if item["variant_key"] == "full"), {})
    best = ranked[0] if ranked else {}
    full_pr = (full.get("metrics") or {}).get("pr_auc")
    best_pr = (best.get("metrics") or {}).get("pr_auc")
    gain = round(float(best_pr) - float(full_pr), 6) if full_pr is not None and best_pr is not None else None
    return {
        "status": "COMPLETED" if ranked else "INSUFFICIENT_DATA",
        "dataset_key": dataset_key,
        "protocol": "identical rolling origins, target, resolution, top-k, labels, and config hash per variant",
        "variants": variants,
        "ranking": [
            {
                "variant_key": item["variant_key"],
                "pr_auc": item["metrics"].get("pr_auc"),
                "roc_auc": item["metrics"].get("roc_auc"),
                "precision_at_k": item["metrics"].get("precision_at_k"),
                "recall_at_k": item["metrics"].get("recall_at_k"),
            }
            for item in ranked
        ],
        "best_variant": best.get("variant_key"),
        "best_minus_full_pr_auc": gain,
        "interpretation": (
            "No ablation variant improved PR-AUC over the full model."
            if gain is not None and gain <= 0
            else "Ablation variants with higher PR-AUC require separate validation "
            "before any model change; this run does not activate a model."
        ),
        "limitations": [
            "Leave-one-out and single-factor variants remove both signal and weight; "
            "renormalization changes the meaning of the remaining score.",
            "Ablation differences are descriptive because folds overlap.",
            "Infrastructure and dependency variants are underpowered when those "
            "metadata sources are absent from the isolated validation database.",
            "No variant is registered or activated by this study.",
        ],
        "runtime_ms": round((time.perf_counter() - started) * 1000, 1),
    }
