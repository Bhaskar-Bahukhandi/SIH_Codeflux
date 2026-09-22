from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import get_settings
from app.evaluation.ocr import evaluate_ocr_manifest, ocr_gate_failures
from app.services.ocr_engine import OcrBackendUnavailable, build_ocr_engine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate CODEFLUX OCR against a manifest-driven dataset."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--require-real-package", type=int, default=0)
    parser.add_argument("--require-labeled-real", type=int, default=0)
    parser.add_argument("--max-real-cer", type=float, default=None)
    parser.add_argument("--max-real-wer", type=float, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()

    try:
        engine = build_ocr_engine(settings)
    except OcrBackendUnavailable as exc:
        raise SystemExit(
            "OCR runtime is unavailable. Install/configure the OCR extra "
            "and its compatible inference engine before validation."
        ) from exc

    report = evaluate_ocr_manifest(
        args.manifest,
        settings=settings,
        engine=engine,
    )
    failures = ocr_gate_failures(
        report,
        require_real_package=args.require_real_package,
        require_labeled_real=args.require_labeled_real,
        max_real_cer=args.max_real_cer,
        max_real_wer=args.max_real_wer,
    )
    report["requested_gates"] = {
        "require_real_package": args.require_real_package,
        "require_labeled_real": args.require_labeled_real,
        "max_real_cer": args.max_real_cer,
        "max_real_wer": args.max_real_wer,
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
        "OCR validation complete: "
        f"{report['case_count']} cases; "
        f"{report['dataset_counts']['real_package']} real_package; "
        f"{report['real_package_labeled_count']} labeled real; "
        f"report={output}"
    )

    if failures:
        raise SystemExit(
            "OCR validation gates failed: " + "; ".join(failures)
        )


if __name__ == "__main__":
    main()
