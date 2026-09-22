# Phase 2 — Capture and Evidence Storage

Status: Implementation complete; real-package validation pending

## Goal

Accept real package images as inspection evidence, preserve original bytes, assess capture quality, and prepare safe derivatives for later OCR.

## Slice A — original evidence ingestion

Implemented:

- authenticated image upload to an officer-owned draft inspection;
- multiple capture view types;
- JPEG/PNG/WebP verification using decoded image content;
- generated storage keys;
- SHA-256 checksum;
- width/height, MIME type and size metadata;
- protected capture listing/retrieval;
- upload audit event;
- replaceable local filesystem storage adapter.

## Slice B — image quality and preprocessing foundation

Implemented:

- original-evidence SHA-256 integrity check before processing;
- EXIF orientation normalization;
- separate normalized JPEG derivative;
- derivative checksum, metadata and processing version;
- OpenCV/Pillow sharpness, brightness/exposure and glare heuristics;
- configurable thresholds;
- `pass`, `review_recommended`, `retake_recommended`;
- append-only quality-assessment history;
- protected derivative/quality access;
- processing audit event.

See `docs/phase-2/image-quality.md`.

## Slice C — conservative perspective geometry

Implemented:

- normalized-derivative integrity verification;
- dominant quadrilateral detection;
- area/angle/geometry heuristic scores;
- explicit `not_detected`, `review_recommended`, `correction_available` states;
- separate perspective-corrected derivative only when the safety gate passes;
- stored corner coordinates, threshold snapshot and algorithm version;
- normalized-image fallback when correction is unavailable;
- geometry-analysis audit event.

See `docs/phase-2/perspective-geometry.md`.

## Slice D — reproducible validation harness

Implemented:

- manifest-driven evaluation runner;
- explicit separation of `real_package`, `synthetic` and `other` cases;
- per-image quality/geometry outputs;
- algorithm-version and threshold snapshots in the report;
- optional human-reviewed expected states;
- status agreement metrics only where labels exist;
- warnings when real-package/labeled-real evidence is missing;
- configurable CLI gates for a team-selected validation run.

See `evaluation/phase2/README.md`.

## Evidence rule

The original uploaded image is immutable evidence.

Any preprocessing, OCR preparation or geometric correction creates a new derivative. Existing evidence/derivatives are not silently replaced.

## Important boundaries

Image-quality and geometry results are engineering guidance. They are **not** Legal Metrology findings and are not calibrated model probabilities.

A curved/flexible package may remain uncorrected. OCR must retain the normalized derivative as a fallback.

Synthetic fixtures prove regression behavior only. Phase 2 thresholds remain provisional until a real-package image set is actually evaluated and reviewed.

## Explicitly not implemented yet

- OCR;
- text/label-region extraction;
- declaration extraction;
- font-size/physical measurement;
- compliance decisions.

## Phase 2 exit condition

Implementation can be merged when automated regression tests pass.

Field-validation closure still requires a real-package dataset run using the validation harness. Until that evidence exists, documentation must say **real-package validation pending** rather than claim the capture-quality/geometry thresholds are field-validated.

The OCR phase may begin using normalized/perspective derivatives with provenance, but it must not depend on unproven quality thresholds as a hard legal/compliance gate.
