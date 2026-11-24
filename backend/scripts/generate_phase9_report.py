"""Generate the Phase 9 research report from persisted experiment records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import get_session_factory  # noqa: E402
from app.validation.research_report import build_research_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path (defaults to stdout).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when no Phase 9 experiment records exist.",
    )
    args = parser.parse_args()
    session = get_session_factory()()
    try:
        report = build_research_report(session)
    finally:
        session.close()
    if args.strict and not report.get("dataset_count"):
        print("No Phase 9 experiments are persisted.", file=sys.stderr)
        return 2
    payload = json.dumps(report, indent=2, sort_keys=True, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())