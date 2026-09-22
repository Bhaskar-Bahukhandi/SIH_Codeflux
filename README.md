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

**Phase 3 — OCR text-evidence and evaluation foundation**

Implemented foundation now includes:

- persisted/authenticated inspection workflow;
- immutable package-image evidence;
- protected media storage and SHA-256 integrity checks;
- normalized and perspective-corrected derivatives with explicit fallback;
- versioned image-quality and geometry assessments;
- reproducible Phase 2 validation harness;
- append-only OCR runs with source provenance;
- ordered OCR blocks with recognition score and polygon;
- PaddleOCR runtime adapter behind a testable OCR interface;
- reproducible OCR evaluation harness with CER/WER and real/synthetic evidence separation.

The project still does **not** claim declaration extraction, physical font-size measurement, Legal Metrology rule execution, final reports or offline synchronization.

Real-package image-quality/geometry and OCR validation remain evidence gates. Synthetic tests are regression evidence only.

OCR output is evidence only. Recognition score is an OCR-engine score, not a calibrated legal confidence value, and OCR failure does not by itself prove a mandatory declaration is absent.

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
