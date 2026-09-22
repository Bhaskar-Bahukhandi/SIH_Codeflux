# Backend API

Technology: Python + FastAPI.

The API contains the completed Phase 1 data/access foundation and the current Phase 2 evidence/preprocessing foundation.

## Current capabilities

- liveness and database readiness;
- versioned Alembic migrations;
- Officer / Supervisor / Admin users;
- Argon2 password hashing and JWT authentication;
- officer-owned inspection lifecycle;
- supervisor/admin read access;
- append-only inspection audit events;
- authenticated package-image upload;
- decoded JPEG/PNG/WebP verification;
- original-image SHA-256 and metadata;
- protected original evidence retrieval;
- original-evidence integrity verification before processing;
- EXIF orientation-normalized derivative creation;
- OpenCV/Pillow image-quality metrics;
- versioned quality assessments with stored threshold snapshots;
- protected derivative and latest-quality retrieval;
- conservative quadrilateral geometry analysis;
- optional perspective-corrected derivative with normalized-image fallback.

OCR, declaration extraction, physical measurement, Legal Metrology rule execution, reports and offline sync are not represented as working yet.

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

## Evidence-storage rule

Original uploaded images are immutable evidence. Preprocessing writes a separate derivative.

Before processing, the stored original is re-hashed and compared with the database checksum. An integrity mismatch blocks processing.

## Quality-processing endpoints

For an authenticated, officer-owned draft inspection:

- `POST /api/v1/inspections/{inspection_id}/captures/{capture_id}/process`
- `GET /api/v1/inspections/{inspection_id}/captures/{capture_id}/quality/latest`
- `GET /api/v1/inspections/{inspection_id}/captures/{capture_id}/derivatives/{derivative_id}/content`

Supervisors/admins may read processed evidence through the existing visibility rules, but processing/mutation remains an officer action.

## Quality rule

The v1 quality status is capture guidance only. It must never be translated into a compliance violation.

## Database rule

PostgreSQL remains the production target. SQLite in tests is isolated test infrastructure. Schema changes use Alembic migrations.


## Geometry endpoints

After capture preprocessing:

- `POST /api/v1/inspections/{inspection_id}/captures/{capture_id}/geometry/analyze`
- `GET /api/v1/inspections/{inspection_id}/captures/{capture_id}/geometry/latest`

Geometry analysis can return `not_detected`, `review_recommended`, or `correction_available`.

Only the last state creates a new `perspective_corrected` derivative. The normalized derivative remains the fallback in every case.

Geometry scores are engineering heuristics, not probabilities or legal conclusions.
