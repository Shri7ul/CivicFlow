"""Generate a reproducibility report from persisted validation experiments.

Examples:
  .venv/Scripts/python.exe scripts/generate_validation_report.py --latest
  .venv/Scripts/python.exe scripts/generate_validation_report.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.db.session import get_session_factory  # noqa: E402
from app.models import ValidationDataset, ValidationExperiment  # noqa: E402
from app.validation.service import build_report  # noqa: E402


def _table(report: dict) -> list[str]:
    metrics = report["metrics"] or {}
    methods = metrics.get("methods", {})
    if not methods:
        return []
    lines = [
        "| Method | PR-AUC | ROC-AUC | Precision@k | Recall@k | Folds |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, values in methods.items():
        lines.append(
            f"| {name} | {values.get('pr_auc')} | {values.get('roc_auc')} | "
            f"{values.get('precision_at_k')} | {values.get('recall_at_k')} | "
            f"{values.get('completed_folds')}/{values.get('fold_count')} |"
        )
    return lines


def _markdown(report: dict) -> str:
    lines = [
        f"# Validation report · {report['name']}",
        "",
        f"- Experiment key: `{report['experiment_key']}`",
        f"- Status: **{report['status']}**",
        f"- Experiment type: `{report['experiment_type']}`",
        f"- Evidence kind: `{report['evidence_kind']}`",
        f"- Method: {report['methodology']['method']}",
        f"- Split: {report['methodology']['split_method'] or 'n/a'}",
        f"- Model: {report['methodology']['model_name'] or 'n/a'} "
        f"{report['methodology']['model_version'] or ''}",
        f"- Config hash: `{report['methodology']['config_hash'] or 'n/a'}`",
        f"- Started: {report['started_at']}",
        f"- Completed: {report['completed_at'] or 'n/a'}",
        "",
        "## Executive summary",
        "",
        report["executive_summary"],
        "",
    ]
    dataset = report.get("dataset")
    if dataset:
        lines.extend(
            [
                "## Dataset and provenance",
                "",
                f"- Name: {dataset['name']}",
                f"- Source: {dataset['source_url']}",
                f"- Region: {dataset['region']}",
                f"- Period: {dataset['period_start']} to {dataset['period_end']}",
                f"- Records: {dataset['record_count']}",
                f"- Schema: {dataset['schema_version']}",
                f"- Snapshot SHA-256: `{dataset['snapshot_sha256']}`",
                f"- License note: {dataset['license_note']}",
                "",
            ]
        )
    table = _table(report)
    if table:
        lines.extend(["## Baseline comparison", "", *table, ""])
    sensitivity = (report["metrics"] or {}).get("sensitivity")
    if isinstance(sensitivity, dict):
        lines.extend(
            [
                "## Sensitivity",
                "",
                f"- Main resolution: H3-{sensitivity.get('main_resolution')}",
                f"- Window diagnostics: "
                f"`{json.dumps(sensitivity.get('window_168_vs_336'), sort_keys=True)}`",
                f"- Resolution diagnostics: "
                f"`{json.dumps(sensitivity.get('resolution'), sort_keys=True)}`",
                f"- Risk-band counts: "
                f"`{json.dumps(sensitivity.get('thresholds'), sort_keys=True)}`",
                "",
            ]
        )
    lines.extend(["## Findings", ""])
    lines.extend(f"- {item}" for item in report["findings"])
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.extend(
        [
            "",
            "## Reproducibility",
            "",
            "```json",
            json.dumps(report["reproducibility"], indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-key")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    session = get_session_factory()()
    try:
        statement = select(ValidationExperiment).order_by(
            ValidationExperiment.completed_at.desc()
        )
        if args.experiment_key:
            statement = statement.where(
                ValidationExperiment.experiment_key == args.experiment_key
            )
        experiments = list(session.scalars(statement).all())
        if not args.all:
            experiments = experiments[:1]
        if not experiments:
            raise SystemExit("No matching validation experiments.")
        reports = []
        for experiment in experiments:
            dataset = (
                session.get(ValidationDataset, experiment.dataset_id)
                if experiment.dataset_id
                else None
            )
            reports.append(build_report(experiment, dataset))
        if args.json:
            output = json.dumps(
                reports if args.all else reports[0], indent=2, sort_keys=True
            )
        else:
            output = "\n\n---\n\n".join(_markdown(item) for item in reports)
        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
        else:
            print(output)
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
