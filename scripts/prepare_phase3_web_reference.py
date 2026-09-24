from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from prepare_phase2_web_reference import download_image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download the curated official package web references and build "
            "an unlabeled Phase 3 OCR observation manifest."
        )
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("evaluation/phase2/web_reference_sources.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation/phase3"),
    )
    parser.add_argument("--retries", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    registry_path = (
        args.registry if args.registry.is_absolute() else repo_root / args.registry
    ).resolve()
    output_dir = (
        args.output_dir if args.output_dir.is_absolute() else repo_root / args.output_dir
    ).resolve()
    images_dir = output_dir / "images"
    manifest_path = output_dir / "manifest.csv"
    acquisition_path = output_dir / "web_reference_acquisition.json"

    if not registry_path.is_file():
        raise FileNotFoundError(f"Web-reference registry not found: {registry_path}")

    with registry_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise ValueError("Web-reference registry contains no rows.")

    required = {
        "case_id",
        "image_filename",
        "asset_url",
        "source_page_url",
        "notes",
    }
    missing = required - set(rows[0])
    if missing:
        raise ValueError(
            "Web-reference registry is missing columns: "
            + ", ".join(sorted(missing))
        )

    seen_case_ids: set[str] = set()
    acquisition: list[dict] = []
    manifest_rows: list[dict[str, str]] = []

    for row in rows:
        case_id = (row.get("case_id") or "").strip()
        image_filename = (row.get("image_filename") or "").strip()
        asset_url = (row.get("asset_url") or "").strip()
        source_page_url = (row.get("source_page_url") or "").strip()
        notes = (row.get("notes") or "").strip()

        if not all((case_id, image_filename, asset_url, source_page_url)):
            raise ValueError(f"Incomplete web-reference row: {row}")
        if case_id in seen_case_ids:
            raise ValueError(f"Duplicate case_id in web-reference registry: {case_id}")
        seen_case_ids.add(case_id)

        destination = images_dir / image_filename
        result = download_image(asset_url, destination, args.retries)
        acquisition.append(
            {
                "case_id": case_id,
                "image_filename": image_filename,
                "asset_url": asset_url,
                "source_page_url": source_page_url,
                **result,
            }
        )
        manifest_rows.append(
            {
                "case_id": case_id,
                "image_path": f"images/{image_filename}",
                "dataset_type": "web_reference",
                "ground_truth_path": "",
                "notes": notes,
                "source_page_url": source_page_url,
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_id",
                "image_path",
                "dataset_type",
                "ground_truth_path",
                "notes",
                "source_page_url",
            ],
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    acquisition_payload = {
        "registry": registry_path.name,
        "registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
        "case_count": len(acquisition),
        "cases": acquisition,
    }
    acquisition_path.write_text(
        json.dumps(acquisition_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(
        f"Prepared {len(acquisition)} OCR web-reference cases; "
        f"manifest={manifest_path}; acquisition={acquisition_path}"
    )


if __name__ == "__main__":
    main()
