# Backend API

Technology: Python + FastAPI.

This service is the central API foundation for persisted inspection data.

## Current Phase 1 capabilities

- application factory;
- `GET /health`;
- SQLAlchemy database foundation;
- Alembic migrations;
- inspection persistence;
- create/list/get inspection endpoints;
- draft inspection editing;
- draft -> pending-review submission;
- user/role persistence foundation;
- stable domain error shape for 404/409 cases;
- isolated API/persistence tests.

No OCR, Legal Metrology rule, report, authentication, or sync behavior is represented as working yet.

## Local setup

From `services/api`:

```bash
python -m venv .venv
# activate the virtual environment
pip install -e ".[dev]"
```

Create a local `.env` from the repository `.env.example` and configure `DATABASE_URL`.

Apply migrations:

```bash
alembic upgrade head
```

Run the API:

```bash
uvicorn app.main:app --reload
```

Run tests:

```bash
pytest
```

## Database rule

PostgreSQL remains the production target. SQLite in tests is an isolated test dependency.

Schema changes must use Alembic migrations. Runtime code must not silently recreate or mutate the production schema.

## Lifecycle rule

The API currently supports `draft -> pending_review`.

There is deliberately no finalize endpoint yet. Finalization will be introduced only when the officer-review/report phase has the data required to make finalization meaningful.
