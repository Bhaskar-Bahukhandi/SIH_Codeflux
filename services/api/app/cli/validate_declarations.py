from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.evaluation.declarations import (
    declaration_gate_failures,
    evaluate_declaration_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate deterministic declaration extraction."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--require-real-actual-ocr", type=int, default=0)
    parser.add_argument("--min-real-exact-match-rate", type=float, default=None)
    parser.add_argument("--min-overall-precision", type=float, default=None)
    parser.add_argument("--min-overall-recall", type=float, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = evaluate_declaration_manifest(args.manifest)
    failures = declaration_gate_failures(
        report,
        require_real_actual_ocr=args.require_real_actual_ocr,
        min_real_exact_match_rate=args.min_real_exact_match_rate,
        min_overall_precision=args.min_overall_precision,
        min_overall_recall=args.min_overall_recall,
    )
    report["requested_gates"] = {
        "require_real_actual_ocr": args.require_real_actual_ocr,
        "min_real_exact_match_rate": args.min_real_exact_match_rate,
        "min_overall_precision": args.min_overall_precision,
        "min_overall_recall": args.min_overall_recall,
    }
    report["gate_failures"] = failures
    report["gates_passed"] = not failures

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(
        "Declaration validation complete: "
        f"{report['case_count']} cases; "
        f"{report['real_package_actual_ocr_case_count']} "
        "real-package actual-OCR; "
        f"report={output}"
    )

    if failures:
        raise SystemExit(
            "Declaration validation gates failed: " + "; ".join(failures)
        )


if __name__ == "__main__":
    main()
