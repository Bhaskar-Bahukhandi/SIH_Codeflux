# Backend API

Technology: Python + FastAPI.

This service is the central API foundation for persisted inspection data. It is intentionally small in the first Phase 1 slice.

## Current Phase 1 slice

Implemented in this branch:

- application factory;
- `GET /health`;
- SQLAlchemy database foundation;
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

Initialize the current development schema:

```bash
python -m app.db_init
```

Run the API:

```bash
uvicorn app.main:app --reload
```

Run tests:

```bash
pytest
```

## Important limitation

`db_init` uses SQLAlchemy metadata creation only as an early Phase 1 bootstrap. A proper migration baseline must replace this before the schema is treated as stable.

The production target remains PostgreSQL. SQLite in the tests is an isolated test dependency and does not change that architecture decision.
