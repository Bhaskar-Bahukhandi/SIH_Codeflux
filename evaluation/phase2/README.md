# Phase 2 Validation Dataset

This directory defines the reproducible validation format for the provisional image-quality and perspective-geometry heuristics.

## Why this exists

The automated tests prove deterministic code behavior on synthetic fixtures. They do **not** prove that the thresholds work well on real retail-package photographs.

A real-package dataset must therefore be evaluated separately before the team makes field-performance claims.

Before collecting/labeling images, follow [COLLECTION_PROTOCOL.md](./COLLECTION_PROTOCOL.md). Human expected labels should be assigned before inspecting CODEFLUX predictions to reduce confirmation bias.

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
| `dataset_type` | yes | `real_package`, `web_reference`, `synthetic`, or `other` |
| `expected_quality_status` | no | Human-reviewed expected quality outcome |
| `expected_geometry_status` | no | Human-reviewed expected geometry outcome |
| `source_page_url` | required for `web_reference` | Official/public page from which the reference image was obtained |
| `notes` | yes (may be blank) | Context such as glare, blur, curved pack, difficult angle |

Supported expected quality statuses:

- `pass`
- `review_recommended`
- `retake_recommended`

Supported expected geometry statuses:

- `not_detected`
- `review_recommended`
- `correction_available`

## Dataset classes

- `real_package`: a camera photograph of a physical package in a real/field-like setup. It may be locally collected or an openly licensed public photograph when its source/capture provenance is retained. Publicly sourced physical-package photographs prove camera/package diversity, not execution through the CODEFLUX mobile camera.
- `web_reference`: an image obtained from a public product/manufacturer page, typically a marketing/studio asset. Useful for packaging diversity and observation, but it does **not** count toward the real-package gate.
- `synthetic`: generated or constructed regression fixture.
- `other`: anything that does not fit the above categories.

For `web_reference`, `source_page_url` is mandatory. The report derives and records the source domain, while the real-package counters remain separate.

## Run

From `services/api`:

```bash
python -m app.cli.validate_phase2 \
  --manifest ../../evaluation/phase2/manifest.csv \
  --output ../../evaluation/reports/phase2-validation.json
```

The report records:

- manifest filename and SHA-256;
- manifest-relative image paths and per-image SHA-256 digests;
- an input-provenance schema version;
- algorithm versions;
- exact threshold snapshots;
- real/web-reference/synthetic/other case counts;
- per-image metrics and states;
- status agreement only for cases that have expected labels;
- separate web-reference agreement summaries and source-domain inventory;
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
- Web-reference cases are stronger than synthetic fixtures for packaging diversity, but they are not field-camera evidence and never satisfy the real-package count gate.
- Unlabeled real images show observed metrics/states but cannot support an accuracy/agreement claim.
- The checked-in public-physical registry contains source-page, author and license provenance but no human expected quality/geometry labels. Its workflow is therefore a real-package **observation** gate, not an agreement/accuracy gate.
- Public physical-package photographs do not prove capture through the CODEFLUX mobile app; that remains part of the separate physical-device validation gate.
- The harness reports status agreement, not calibrated model accuracy.
- Threshold tuning must be documented; material behavior changes require a new algorithm version.
- SHA-256 provenance identifies the exact manifest and image bytes used by a report; it does not replace human review of dataset suitability.
