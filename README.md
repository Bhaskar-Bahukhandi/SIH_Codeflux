# SIH Codeflux — Legal Metrology Compliance System

Smart India Hackathon 2026  
Problem Statement ID: **SIH26034**

## Project goal

Build a practical inspection-assistance system for packaged commodities under the Legal Metrology (Packaged Commodities) Rules, 2011.

The core workflow is:

1. Capture product details and multiple package images.
2. Pre-process images for orientation, perspective and readability.
3. Extract visible text using OCR.
4. Identify relevant declarations such as MRP, net quantity, manufacturer/packer/importer details, dates and consumer information.
5. Combine evidence from multiple package views.
6. Run versioned preliminary Legal Metrology checks.
7. Let the officer verify, correct or recheck flagged findings.
8. Generate an evidence-backed inspection report and retain inspection history.
9. Support offline field work with later synchronization.
10. Provide a dashboard for search, status, monitoring and export.

## Project principles

- Officer verification remains the final decision gate.
- Automated outputs must be traceable to image evidence and rule references.
- Low-confidence or unsupported cases must be marked for review instead of guessed.
- Legal checks must be implemented from verified official sources.
- Core functionality must use real persisted data; no fake demo buttons or hard-coded compliance results.
- Optional future ideas stay outside the SIH core unless the team explicitly moves them into scope.

## Current status

**Phase 2 — Capture and evidence storage**

Phase 1 is complete and validated.

Current Phase 2 work adds the first real package-image evidence path:

- officer-owned draft inspections can receive multiple images;
- original supported images are preserved byte-for-byte;
- file type is verified from decoded image content;
- SHA-256, dimensions, size, view type and uploader are stored;
- inspection media remains behind authenticated access;
- capture upload is audit-traced.

This phase does **not** yet claim image-quality scoring, preprocessing, OCR, declaration extraction or Legal Metrology compliance results.

## Technical baseline

- Mobile field app: Flutter
- Web dashboard: React
- Backend: Python + FastAPI
- Computer vision / OCR: OpenCV + PaddleOCR
- Central database: PostgreSQL
- Offline local data: SQLite + local file storage

## Repository workflow

Development is staged and reversible:

- `main` stays stable.
- Work is done on phase/feature branches.
- Each phase has an explicit acceptance gate.
- Validation evidence is required before a phase is considered complete.
- Failed experiments should not replace the last known-good path.

## Scope note

This repository is for the SIH26034 enforcement-assistance prototype. Manufacturer portals, consumer scanners, e-commerce integrations, blockchain, RAG assistants and broader regulatory modules are not part of the current core build.
