# Backend API

Technology: Python + FastAPI.

The API contains the data/access, capture/preprocessing, OCR evidence, declaration-extraction and first versioned preliminary rule-evaluation foundations.

## Current capabilities

- liveness and database readiness;
- versioned Alembic migrations;
- Officer / Supervisor / Admin authentication and access control;
- officer-owned inspection lifecycle;
- authenticated package-image upload and immutable original-image provenance;
- normalized/perspective derivatives with fallback;
- versioned image-quality and geometry assessments;
- append-only OCR runs with source/checksum provenance;
- deterministic MRP and net-quantity candidate extraction;
- OCR-block provenance and multi-image conflict preservation;
- versioned source-gated rule pack for Rule 6(1)(c) net quantity evidence and Rule 6(1)(e) MRP evidence;
- persisted rule-pack ID/version/SHA-256 plus a full logical rule-pack snapshot, source extraction run and officer context;
- explicit pass, manual_verification_required, indeterminate, and not_evaluated behavior for the current pack.

Physical measurement, confirmed-absence findings, officer finding approval/finalization, reports and offline sync are not represented as working yet.

## Local setup

From services/api:

    python -m venv .venv
    # activate the virtual environment
    pip install -e ".[dev]"
    alembic upgrade head
    uvicorn app.main:app --reload
    pytest

## OCR runtime

The production OCR adapter uses PaddleOCR 3.x behind a pluggable OCR interface.

    pip install -e ".[ocr]"

OCR output is evidence only. Recognition score is not a calibrated legal-confidence probability.

## Declaration extraction

For an authenticated officer-owned draft inspection:

- POST /api/v1/inspections/{inspection_id}/declarations/extract
- GET /api/v1/inspections/{inspection_id}/declarations/latest

Initial supported types:

- MRP / retail sale price;
- net quantity.

Fusion states:

- not_detected
- single_source
- consistent
- conflict

A conflict is never resolved by silently choosing one value.

## Preliminary rule evaluation

Endpoints:

- POST /api/v1/inspections/{inspection_id}/rule-evaluations/evaluate
- GET /api/v1/inspections/{inspection_id}/rule-evaluations/latest

The current request supplies factual applicability context:

    {
      "context": {
        "intended_for_retail_sale": true,
        "industrial_or_institutional_consumer": false,
        "package_exceeds_25kg_or_25l": false
      }
    }

The first rule pack is lmpc-retail-evidence@2026.09-v1.

It evaluates only preliminary declaration evidence for Rule 6(1)(c) and Rule 6(1)(e).

### Critical semantics

- detected single/consistent evidence -> pass for the preliminary evidence check;
- conflicting values -> manual_verification_required;
- not_detected -> manual_verification_required, never automatic non-compliance;
- incomplete context -> indeterminate;
- unsupported context -> not_evaluated.

Rule evaluation is rejected if the declaration extraction has become stale after capture/preprocessing/OCR changes.

## Legal boundary

The current rule engine does not issue a final legal verdict, penalty or notice.

A pass means the current declaration-evidence check passed under the recorded rule pack/context. It does not certify the package as fully compliant.

## Database rule

PostgreSQL remains the production target. SQLite in tests is isolated test infrastructure. Schema changes use Alembic migrations.
