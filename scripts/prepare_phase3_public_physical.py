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
            "Download curated licensed physical-package photographs and build "
            "an unlabeled Phase 3 real-package OCR observation manifest."
        )
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("evaluation/phase2/public_physical_sources.csv"),
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
    acquisition_path = output_dir / "public_physical_acquisition.json"

    with registry_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("Public physical-package registry contains no rows.")

    required = {
        "case_id",
        "image_filename",
        "asset_url",
        "source_page_url",
        "author",
        "license",
        "notes",
    }
    missing = required - set(rows[0])
    if missing:
        raise ValueError(
            "Public physical-package registry is missing columns: "
            + ", ".join(sorted(missing))
        )

    seen: set[str] = set()
    acquisition: list[dict] = []
    manifest_rows: list[dict[str, str]] = []

    for row in rows:
        values = {key: (row.get(key) or "").strip() for key in required}
        if not all(values.values()):
            raise ValueError(f"Incomplete public physical-package row: {row}")
        case_id = values["case_id"]
        if case_id in seen:
            raise ValueError(f"Duplicate case_id: {case_id}")
        seen.add(case_id)

        destination = images_dir / values["image_filename"]
        result = download_image(values["asset_url"], destination, args.retries)
        acquisition.append(
            {
                "case_id": case_id,
                "image_filename": values["image_filename"],
                "asset_url": values["asset_url"],
                "source_page_url": values["source_page_url"],
                "author": values["author"],
                "license": values["license"],
                **result,
            }
        )
        manifest_rows.append(
            {
                "case_id": case_id,
                "image_path": f"images/{values['image_filename']}",
                "dataset_type": "real_package",
                "ground_truth_path": "",
                "notes": (
                    f"{values['notes']}; author={values['author']}; "
                    f"license={values['license']}"
                ),
                "source_page_url": values["source_page_url"],
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
        "evidence_class": "public_physical_package_camera_photograph",
        "ground_truth_state": "unlabeled",
        "cases": acquisition,
    }
    acquisition_path.write_text(
        json.dumps(acquisition_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(
        f"Prepared {len(acquisition)} real-package OCR observation cases; "
        f"manifest={manifest_path}"
    )


if __name__ == "__main__":
    main()
