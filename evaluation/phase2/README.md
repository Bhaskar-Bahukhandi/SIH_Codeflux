# Phase 2 Validation Dataset

This directory defines the reproducible validation format for the provisional image-quality and perspective-geometry heuristics.

## Why this exists

The automated tests prove deterministic code behavior on synthetic fixtures. They do **not** prove that the thresholds work well on real retail-package photographs.

A real-package dataset must therefore be evaluated separately before the team makes field-performance claims.

## Local dataset layout

Keep real images outside Git:

```text
evaluation/phase2/
  manifest.csv
  images/
    package-001.jpg
    package-002.jpg
    ...
```

The repository `.gitignore` excludes `evaluation/phase2/images/` and generated reports so package photos are not accidentally committed.

## Manifest columns

| Column | Required | Meaning |
| --- | --- | --- |
| `case_id` | yes | Stable unique case identifier |
| `image_path` | yes | Path relative to the manifest file |
| `dataset_type` | yes | `real_package`, `synthetic`, or `other` |
| `expected_quality_status` | no | Human-reviewed expected quality outcome |
| `expected_geometry_status` | no | Human-reviewed expected geometry outcome |
| `notes` | yes (may be blank) | Context such as glare, blur, curved pack, difficult angle |

Supported expected quality statuses:

- `pass`
- `review_recommended`
- `retake_recommended`

Supported expected geometry statuses:

- `not_detected`
- `review_recommended`
- `correction_available`

## Run

From `services/api`:

```bash
python -m app.cli.validate_phase2 \
  --manifest ../../evaluation/phase2/manifest.csv \
  --output ../../evaluation/reports/phase2-validation.json
```

The report records:

- algorithm versions;
- exact threshold snapshots;
- real/synthetic/other case counts;
- per-image metrics and states;
- status agreement only for cases that have expected labels;
- mismatch case IDs;
- warnings when real-package or labeled-real-package evidence is missing.

## Gates

The CLI can enforce dataset minimums chosen by the team for a particular validation run:

```bash
python -m app.cli.validate_phase2 \
  --manifest ../../evaluation/phase2/manifest.csv \
  --output ../../evaluation/reports/phase2-validation.json \
  --require-real-package 20 \
  --require-labeled-real-quality 20 \
  --require-labeled-real-geometry 20 \
  --fail-on-mismatch
```

Those numbers are an **example invocation**, not a hard-coded project requirement.

## Honest interpretation

- Synthetic cases are regression evidence only.
- Unlabeled real images show observed metrics/states but cannot support an accuracy/agreement claim.
- The harness reports status agreement, not calibrated model accuracy.
- Threshold tuning must be documented; material behavior changes require a new algorithm version.
