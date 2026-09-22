from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import get_settings
from app.evaluation.phase2 import evaluate_phase2_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate Phase 2 image-quality and geometry heuristics "
            "against a manifest-driven dataset."
        )
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--require-real-package",
        type=int,
        default=0,
        help="Fail if fewer than this many real_package cases are present.",
    )
    parser.add_argument(
        "--require-labeled-real-quality",
        type=int,
        default=0,
        help=(
            "Fail if fewer than this many real_package cases have "
            "expected quality labels."
        ),
    )
    parser.add_argument(
        "--require-labeled-real-geometry",
        type=int,
        default=0,
        help=(
            "Fail if fewer than this many real_package cases have "
            "expected geometry labels."
        ),
    )
    parser.add_argument(
        "--fail-on-mismatch",
        action="store_true",
        help="Exit non-zero when any supplied expected status does not match.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = evaluate_phase2_manifest(
        args.manifest,
        settings=get_settings(),
    )

    real_count = report["dataset_counts"]["real_package"]
    if real_count < args.require_real_package:
        raise SystemExit(
            f"Real-package gate failed: {real_count} < "
            f"{args.require_real_package}."
        )

    quality_real = report["real_package_labeled_quality_count"]
    if quality_real < args.require_labeled_real_quality:
        raise SystemExit(
            f"Labeled real-package quality gate failed: {quality_real} < "
            f"{args.require_labeled_real_quality}."
        )

    geometry_real = report["real_package_labeled_geometry_count"]
    if geometry_real < args.require_labeled_real_geometry:
        raise SystemExit(
            f"Labeled real-package geometry gate failed: {geometry_real} < "
            f"{args.require_labeled_real_geometry}."
        )

    if args.fail_on_mismatch:
        mismatches = (
            report["quality_status_agreement"]["mismatch_case_ids"]
            + report["geometry_status_agreement"]["mismatch_case_ids"]
        )
        if mismatches:
            raise SystemExit(
                "Expected-status mismatches: "
                + ", ".join(sorted(set(mismatches)))
            )

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(
        "Phase 2 validation complete: "
        f"{report['case_count']} cases; "
        f"{real_count} real_package; "
        f"report={output}"
    )


if __name__ == "__main__":
    main()
