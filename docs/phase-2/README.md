# Phase 2 — Capture and Evidence Storage

Status: In progress

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

## Evidence rule

The original uploaded image is immutable evidence.

Any preprocessing, OCR preparation or geometric correction creates a new derivative. Existing evidence/derivatives are not silently replaced.

## Important boundaries

Image-quality and geometry results are engineering guidance. They are **not** Legal Metrology findings and are not calibrated model probabilities.

A curved/flexible package may remain uncorrected. OCR must retain the normalized derivative as a fallback.

## Explicitly not implemented yet

- OCR;
- text/label-region extraction;
- declaration extraction;
- font-size/physical measurement;
- compliance decisions.

## Next Phase 2 work

1. validate quality/geometry behavior on a small real package-image set;
2. keep unsupported/ambiguous geometry on the normalized fallback;
3. then enter the OCR phase with complete source/derivative provenance.
