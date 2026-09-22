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

Implemented in the current branch:

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

## Evidence rule

The original uploaded image is immutable evidence.

Any preprocessing, OCR preparation or later enhancement must create a derivative. Original bytes/checksum must never be silently replaced.

## Important boundary

Image-quality results are engineering guidance for capture usability. They are **not** Legal Metrology findings.

A poor image means retake/review; it does not mean the package is non-compliant.

## Explicitly not implemented yet

- validated perspective correction;
- label/region detection;
- OCR;
- declaration extraction;
- font-size measurement;
- compliance decisions.

## Next Phase 2 work

1. validate quality thresholds on a small real package-image set;
2. add safe perspective/geometry detection only if confidence/failure gates are defensible;
3. then move to the OCR phase with original/derivative provenance intact.
