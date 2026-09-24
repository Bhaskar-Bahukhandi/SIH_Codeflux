from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a successful Phase 3 OCR web-reference report into an "
            "unlabeled Phase 4 declaration-observation manifest."
        )
    )
    parser.add_argument(
        "--ocr-report",
        type=Path,
        default=Path("evaluation/reports/phase3-web-reference-ocr.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/phase4/manifest.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    report_path = (
        args.ocr_report
        if args.ocr_report.is_absolute()
        else repo_root / args.ocr_report
    ).resolve()
    output_path = (
        args.output if args.output.is_absolute() else repo_root / args.output
    ).resolve()

    if not report_path.is_file():
        raise FileNotFoundError(f"OCR report not found: {report_path}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    cases = report.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("OCR report does not contain any cases.")

    if report.get("failed_case_count") != 0:
        raise ValueError(
            "Phase 4 observation requires an OCR report with zero failed cases."
        )

    phase4_cases: list[dict] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("OCR report contains a non-object case.")
        if case.get("dataset_type") != "web_reference":
            raise ValueError(
                "Phase 4 web-reference preparation received a non-web-reference case."
            )
        if case.get("status") != "ok":
            raise ValueError(
                f"OCR case {case.get('case_id')!r} did not complete successfully."
            )

        blocks = case.get("blocks")
        if not isinstance(blocks, list):
            raise ValueError(
                f"OCR case {case.get('case_id')!r} is missing block evidence."
            )

        case_id = str(case.get("case_id") or "").strip()
        source_page_url = str(case.get("source_page_url") or "").strip()
        if not case_id or not source_page_url:
            raise ValueError(
                "OCR web-reference cases require case_id and source_page_url."
            )

        phase4_cases.append(
            {
                "case_id": case_id,
                "dataset_type": "web_reference",
                "block_source": "actual_ocr",
                "source_page_url": source_page_url,
                "ocr_blocks": [
                    {
                        "block_id": f"{case_id}-b{block.get('order_index', index)}",
                        "text": str(block.get("text") or ""),
                        "confidence": float(block.get("confidence")),
                    }
                    for index, block in enumerate(blocks)
                ],
                "expected_declarations": None,
                "notes": (
                    "Unlabeled web-reference declaration observation generated "
                    "from the Phase 3 PaddleOCR report."
                ),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_ocr_report": report_path.name,
        "source_ocr_report_sha256": hashlib.sha256(
            report_path.read_bytes()
        ).hexdigest(),
        "cases": phase4_cases,
    }
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(
        f"Prepared {len(phase4_cases)} Phase 4 web-reference cases; "
        f"manifest={output_path}"
    )


if __name__ == "__main__":
    main()
