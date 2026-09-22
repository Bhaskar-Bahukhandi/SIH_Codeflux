# Backend API

Technology: Python + FastAPI.

The API contains the completed data/access foundation, the capture/preprocessing foundation, and the current OCR text-evidence foundation.

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
- versioned quality assessments with threshold snapshots;
- conservative perspective geometry with normalized fallback;
- append-only OCR runs with source-derivative provenance;
- ordered OCR text blocks with recognition score and polygon;
- protected OCR execution/latest-result access.

Declaration extraction, physical measurement, Legal Metrology rule execution, reports and offline sync are not represented as working yet.

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

Original uploaded images are immutable evidence. Preprocessing writes separate derivatives.

Before OCR, the selected derivative is re-hashed against its stored SHA-256 value. An integrity mismatch blocks OCR.

## OCR runtime

The production OCR adapter uses PaddleOCR 3.x through its `PaddleOCR(...).predict(...)` interface.

Install the Python adapter extra:

```bash
pip install -e ".[ocr]"
```

PaddleOCR local inference also requires a compatible inference engine/runtime. Install that separately according to the official PaddleOCR/PaddlePaddle instructions for the target machine.

Default OCR configuration:

- inference engine: `paddle`;
- language: `en`;
- model family: `PP-OCRv5`;
- device: `cpu`;
- minimum recognition score: `0.0`.

These are engineering/runtime defaults, not Legal Metrology thresholds.

## OCR source selection

OCR uses the latest perspective-corrected derivative only when that correction is based on the latest normalized derivative. Otherwise it falls back to the latest normalized derivative.

A quality status such as `retake_recommended` does not automatically become a legal/compliance failure and does not silently create a missing-declaration result.

## OCR endpoints

For an authenticated officer-owned draft inspection:

- `POST /api/v1/inspections/{inspection_id}/captures/{capture_id}/ocr/run`
- `GET /api/v1/inspections/{inspection_id}/captures/{capture_id}/ocr/latest`

Supervisors/admins may read OCR evidence through the existing inspection visibility model, but OCR execution remains an officer action.

## Database rule

PostgreSQL remains the production target. SQLite in tests is isolated test infrastructure. Schema changes use Alembic migrations.
