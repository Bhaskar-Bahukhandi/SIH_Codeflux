# Backend API

Technology: Python + FastAPI.

The API contains the data/access, capture/preprocessing, OCR text-evidence, and initial declaration-extraction foundations.

## Current capabilities

- liveness and database readiness;
- versioned Alembic migrations;
- Officer / Supervisor / Admin users;
- Argon2 password hashing and JWT authentication;
- officer-owned inspection lifecycle;
- supervisor/admin read access;
- append-only inspection audit events;
- authenticated package-image upload;
- immutable original-image SHA-256 provenance;
- normalized and perspective-corrected derivatives with fallback;
- versioned image-quality and geometry assessments;
- append-only OCR runs with source-derivative provenance;
- ordered OCR text blocks with recognition score and polygon;
- deterministic MRP and net-quantity candidate extraction;
- OCR-block provenance for each extracted observation;
- inspection-level multi-image fusion with explicit conflict preservation.

Physical measurement, Legal Metrology applicability/rule execution, officer finding approval, reports and offline sync are not represented as working yet.

## Local setup

From `services/api`:

```bash
python -m venv .venv
# activate the virtual environment
pip install -e ".[dev]"
```

Create a local `.env` from the repository `.env.example`.

Apply migrations:

```bash
alembic upgrade head
```

Create a prototype officer account:

```bash
python -m app.cli.create_user \
  --email officer@example.test \
  --name "Demo Officer" \
  --role officer
```

Run:

```bash
uvicorn app.main:app --reload
pytest
```

## OCR runtime

The production OCR adapter uses PaddleOCR 3.x behind a pluggable OCR interface.

Install the Python adapter extra:

```bash
pip install -e ".[ocr]"
```

A compatible inference engine/runtime is still required on the target machine.

OCR output is evidence only. Recognition score is not a calibrated legal confidence value.

## Declaration extraction endpoints

For an authenticated officer-owned draft inspection:

- `POST /api/v1/inspections/{inspection_id}/declarations/extract`
- `GET /api/v1/inspections/{inspection_id}/declarations/latest`

The first extractor supports:

- MRP / retail sale price candidates;
- net quantity candidates.

Each observation retains capture, OCR-run and OCR-block provenance plus raw text, normalized value, and the underlying OCR recognition scores.

## Fusion states

- `not_detected`
- `single_source`
- `consistent`
- `conflict`

`consistent` requires the same normalized value on at least two distinct captures.

A conflict is never resolved by silently choosing one value.

## Current-source protection

Extraction uses a capture's latest OCR run only when that OCR run still points to the current OCR source derivative.

If preprocessing changed after OCR, that OCR evidence is recorded as `stale_ocr` and excluded until OCR is rerun.

## Legal boundary

`not_detected` is a technical extraction state only. It does not mean the declaration is legally required, physically absent, or non-compliant.

The current extraction layer contains no Legal Metrology applicability decision or violation logic.

## Database rule

PostgreSQL remains the production target. SQLite in tests is isolated test infrastructure. Schema changes use Alembic migrations.
