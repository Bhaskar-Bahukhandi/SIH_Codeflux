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
            "Download curated openly licensed photographs of physical retail "
            "packages and build an unlabeled Phase 2 real_package manifest."
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
        default=Path("evaluation/phase2"),
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

    seen_case_ids: set[str] = set()
    acquisition: list[dict] = []
    manifest_rows: list[dict[str, str]] = []

    for row in rows:
        normalized = {
            key: (row.get(key) or "").strip()
            for key in required
        }
        if not all(normalized.values()):
            raise ValueError(f"Incomplete public physical-package row: {row}")
        case_id = normalized["case_id"]
        if case_id in seen_case_ids:
            raise ValueError(f"Duplicate case_id: {case_id}")
        seen_case_ids.add(case_id)

        destination = images_dir / normalized["image_filename"]
        result = download_image(
            normalized["asset_url"],
            destination,
            args.retries,
        )
        acquisition.append(
            {
                "case_id": case_id,
                "image_filename": normalized["image_filename"],
                "asset_url": normalized["asset_url"],
                "source_page_url": normalized["source_page_url"],
                "author": normalized["author"],
                "license": normalized["license"],
                **result,
            }
        )
        manifest_rows.append(
            {
                "case_id": case_id,
                "image_path": f"images/{normalized['image_filename']}",
                "dataset_type": "real_package",
                "expected_quality_status": "",
                "expected_geometry_status": "",
                "source_page_url": normalized["source_page_url"],
                "notes": (
                    f"{normalized['notes']}; author={normalized['author']}; "
                    f"license={normalized['license']}"
                ),
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
                "expected_quality_status",
                "expected_geometry_status",
                "source_page_url",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    acquisition_payload = {
        "registry": registry_path.name,
        "registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
        "case_count": len(acquisition),
        "evidence_class": "public_physical_package_camera_photograph",
        "label_state": "unlabeled",
        "cases": acquisition,
    }
    acquisition_path.write_text(
        json.dumps(acquisition_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        f"Prepared {len(acquisition)} public physical-package camera cases; "
        f"manifest={manifest_path}"
    )


if __name__ == "__main__":
    main()
