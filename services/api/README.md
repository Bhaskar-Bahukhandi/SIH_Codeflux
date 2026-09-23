# Backend API

Technology: Python + FastAPI.

The API contains the data/access, capture/preprocessing, OCR evidence, declaration-extraction, preliminary rule-evaluation, Officer verification and finalization/report foundations.

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
- explicit pass, manual_verification_required, indeterminate, and not_evaluated behavior for the current pack;
- immutable finalization snapshots and deterministic evidence-backed PDF reports.

Physical measurement and penalty/notice workflows are not represented as working yet.

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


## Officer rule review

After an inspection is submitted to `pending_review`, its owning Officer may review results from the latest preliminary rule-evaluation run.

Endpoints:

- `POST /api/v1/inspections/{inspection_id}/rule-reviews/{rule_evaluation_result_id}`
- `GET /api/v1/inspections/{inspection_id}/rule-reviews`

Review decisions:

- `accepted` — Officer accepts the current preliminary result for the workflow stage;
- `corrected` — Officer stores a structured corrected value plus a required note;
- `recheck_required` — Officer requires new/reprocessed evidence and records why.

Reviews are append-only and revisioned. OCR, extraction and rule-evaluation records remain immutable.

Supervisor/Admin access remains read-only for these review records in the current prototype.

A review is not a final legal approval, violation finding, penalty or notice.

## Recheck reopening

If the latest review state for at least one result is `recheck_required`, the owning Officer may call:

- `POST /api/v1/inspections/{inspection_id}/reopen-for-recheck`

The inspection returns to `draft` so evidence can be corrected or recaptured.

After reopening, another submission is blocked until a new preliminary rule-evaluation run has been created after the reopen timestamp. This is an evidence-freshness workflow gate, not a legal-compliance decision.

## Finalization and evidence-backed report

After all results in the latest current rule-evaluation run have resolvable Officer reviews, the owning Officer may finalize the inspection:

- `POST /api/v1/inspections/{inspection_id}/finalization`
- `GET /api/v1/inspections/{inspection_id}/finalization`
- `GET /api/v1/inspections/{inspection_id}/finalization/report`

Current resolution rules are intentionally narrow:

- machine `pass` + Officer `accepted` -> resolvable;
- machine `pass` + valid Officer `corrected` -> resolvable;
- machine `manual_verification_required` + valid Officer `corrected` -> resolvable;
- `recheck_required`, `indeterminate`, `not_evaluated`, `not_applicable`, and unsupported states -> blocked.

Finalization stores an immutable snapshot containing rule-pack provenance, machine results, Officer reviews/corrections, resolved values and evidence capture references.

The generated PDF is deterministic for the same snapshot. The database stores both the canonical snapshot SHA-256 and the PDF-file SHA-256. The PDF prints the snapshot checksum because a file cannot safely embed its own cryptographic file hash without creating a self-referential checksum problem.

The report is an evidence-backed inspection review record. It does not calculate penalties or issue statutory notices.

## Phase 7 replay-safe synchronization contracts

The Phase 7 branch adds backward-compatible client-generated stable IDs for offline/retry reconciliation.

Supported stable identities:

- inspection creation: optional JSON `id`;
- capture upload: optional multipart `capture_id`;
- preprocessing: optional paired `derivative_id` + `quality_assessment_id`;
- geometry: optional paired `geometry_assessment_id` + candidate `corrected_derivative_id`;
- OCR: optional JSON `id` for the OCR run;
- declaration extraction: optional JSON `id` for the extraction run;
- rule evaluation: optional JSON `id` for the evaluation run;
- Officer rule review: optional JSON `id`.

Exact reconciliation reads added for append-only/composite processing results:

- `GET /api/v1/inspections/{inspection_id}/captures/{capture_id}/process-runs/{quality_assessment_id}`;
- `GET /api/v1/inspections/{inspection_id}/captures/{capture_id}/geometry/runs/{geometry_assessment_id}`;
- `GET /api/v1/inspections/{inspection_id}/captures/{capture_id}/ocr/runs/{run_id}`;
- `GET /api/v1/inspections/{inspection_id}/declarations/runs/{run_id}`;
- `GET /api/v1/inspections/{inspection_id}/rule-evaluations/runs/{run_id}`.

Stable-ID replay confirms an already-persisted operation. It does not deduplicate intentional reruns by matching input values. A deliberate new run must use a new client UUID or omit the optional ID to retain server-generated-ID behavior.

Composite image-processing retries verify persisted derivative integrity before replay success. Client-facing derivative IDs are decoupled from candidate storage object names where concurrent retry cleanup could otherwise damage a winning evidence file.

Submission and recheck reopening remain lifecycle transitions rather than new server records. The Flutter Phase 7 queue reconciles these transitions from persisted inspection status and recheck timestamps before any uncertain retry.

These additions do not alter Legal Metrology rule semantics or turn processing results into final legal findings.
