# Backend API

Technology: Python + FastAPI.

This service is the central API foundation for persisted inspection data. It is intentionally small in the first Phase 1 slice.

## Current Phase 1 slice

Implemented in this branch:

- application factory;
- `GET /health`;
- SQLAlchemy database foundation;
- Alembic migration baseline;
- inspection model with UUID identifier, draft/finalized status and timestamps;
- create/list/get inspection endpoints;
- persistence tests using an isolated in-memory SQLite database.

No OCR, compliance rule, authentication, report or sync behavior is implemented here yet.

## Local setup

From `services/api`:

```bash
python -m venv .venv
# activate the virtual environment
pip install -e ".[dev]"
```

Create a local `.env` from the repository `.env.example` and configure `DATABASE_URL`.

Apply the database schema:

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

PostgreSQL remains the production target. SQLite in the tests is an isolated test dependency and does not change that architecture decision.

Schema changes must be represented by Alembic migrations rather than relying on runtime `create_all` behavior.
