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

**Phase 6 — Officer verification, finalization and evidence-backed reporting**

Implemented foundation now includes:

- persisted/authenticated inspection workflow;
- immutable package-image evidence and protected derivatives;
- versioned image-quality and geometry assessments;
- append-only OCR evidence with source/checksum provenance;
- deterministic MRP and net-quantity extraction with multi-image conflict preservation;
- reproducible quality/geometry, OCR and extraction evaluation harnesses;
- first source-gated rule pack for Rule 6(1)(c) net-quantity evidence and Rule 6(1)(e) MRP evidence;
- rule-pack ID/version/SHA-256 persisted on every evaluation;
- officer-supplied applicability context persisted with the evaluation;
- stale-extraction protection;
- safe preliminary states that do not turn OCR non-detection into an automatic violation;
- append-only Officer review records for the latest preliminary rule results;
- explicit accepted / corrected / recheck-required review decisions;
- structured Officer corrections stored separately from immutable machine evidence;
- finalization gates that require current evidence and resolvable Officer review states;
- immutable finalization snapshots with rule-pack/evidence provenance and SHA-256 integrity;
- deterministic evidence-backed PDF report generation and protected retrieval.

The project still does **not** claim broad declaration coverage, physical font-size measurement, automated penalty/notice issuance or offline synchronization.

A preliminary rule-engine pass remains only an evidence-check result. Finalization locks the reviewed evidence record and report; it does not invent a penalty or statutory notice.

Real-package image-quality/geometry, OCR and declaration-extraction validation remain evidence gates. Synthetic tests are regression evidence only.

## Technical baseline

- Mobile field app: Flutter
- Web dashboard: React
- Backend: Python + FastAPI
- Computer vision / OCR: OpenCV + PaddleOCR
- Central database: PostgreSQL
- Offline local data: SQLite + local file storage

## Repository workflow

Development is staged and reversible:

- main stays stable.
- Work is done on phase/feature branches.
- Each phase has an explicit acceptance gate.
- Validation evidence is required before a phase is considered complete.
- Failed experiments should not replace the last known-good path.

## Scope note

This repository is for the SIH26034 enforcement-assistance prototype. Manufacturer portals, consumer scanners, e-commerce integrations, blockchain, RAG assistants and broader regulatory modules are not part of the current core build.
