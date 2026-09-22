from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import get_settings
from app.evaluation.phase2 import (
    evaluate_phase2_manifest,
    phase2_gate_failures,
)


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

    requested_gates = {
        "require_real_package": args.require_real_package,
        "require_labeled_real_quality": args.require_labeled_real_quality,
        "require_labeled_real_geometry": args.require_labeled_real_geometry,
        "fail_on_mismatch": args.fail_on_mismatch,
    }
    failures = phase2_gate_failures(
        report,
        require_real_package=args.require_real_package,
        require_labeled_real_quality=args.require_labeled_real_quality,
        require_labeled_real_geometry=args.require_labeled_real_geometry,
        fail_on_mismatch=args.fail_on_mismatch,
    )
    report["requested_gates"] = requested_gates
    report["gate_failures"] = failures
    report["gates_passed"] = not failures

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(
        "Phase 2 validation complete: "
        f"{report['case_count']} cases; "
        f"{report['dataset_counts']['real_package']} real_package; "
        f"report={output}"
    )

    if failures:
        raise SystemExit(
            "Validation gates failed: " + "; ".join(failures)
        )


if __name__ == "__main__":
    main()
