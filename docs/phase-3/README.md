# Phase 3 — OCR Text Evidence

Status: In progress

## Goal

Convert prepared package images into traceable text evidence while keeping OCR separate from declaration extraction and legal compliance logic.

## First slice — OCR provenance and persistence

This slice adds:

- a pluggable OCR-engine interface;
- a PaddleOCR 3.x adapter;
- explicit source-derivative selection;
- source derivative/checksum provenance;
- append-only OCR runs;
- ordered text blocks with recognition score and polygon;
- protected OCR execution/latest-result endpoints;
- audit tracing;
- fake-engine tests that do not require model downloads.

## Source selection

OCR uses:

1. the latest perspective-corrected derivative only when that correction is based on the latest normalized derivative;
2. otherwise the latest normalized derivative.

This prevents an older perspective correction from silently overriding newer preprocessing.

## Important boundaries

OCR output is evidence, not a Legal Metrology verdict.

- Recognition score is the OCR engine's score, not a calibrated legal probability.
- Empty/failed OCR does not prove a declaration is absent.
- No declaration normalization or field extraction occurs in this slice.
- No rule engine or compliance finding occurs in this slice.

## PaddleOCR runtime

The adapter targets the current PaddleOCR 3.x `PaddleOCR(...).predict(...)` pipeline and reads the documented `rec_texts`, `rec_scores` and `rec_polys` fields.

The Python package is optional because local inference also depends on a compatible inference engine/runtime. Missing support returns an explicit OCR-backend-unavailable error instead of an empty result.

Official references:

- https://www.paddleocr.ai/main/en/quick_start.html
- https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
- https://www.paddleocr.ai/main/en/version3.x/installation.html

## Next work

After this foundation is validated:

1. run real OCR against representative package photographs;
2. add OCR evaluation metrics/ground truth;
3. only then begin declaration extraction and multi-image fusion.
