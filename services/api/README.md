# Backend API

Technology: Python + FastAPI.

This service is the central API foundation for persisted inspection data.

## Current Phase 1 capabilities

- `GET /health` liveness;
- `GET /health/ready` database readiness;
- SQLAlchemy database foundation;
- Alembic migrations;
- persisted Officer / Supervisor / Admin users;
- Argon2 password hashing;
- JWT login/current-user endpoint;
- protected inspection API;
- officer ownership/read isolation;
- supervisor/admin inspection read access;
- draft editing and `draft -> pending_review` submission;
- append-only audit events for inspection create/update/submit;
- stable domain error responses;
- isolated API/persistence/auth/audit tests.

No OCR, Legal Metrology rule, report, mobile capture, or sync behavior is represented as working yet.

## Local setup

From `services/api`:

```bash
python -m venv .venv
# activate the virtual environment
pip install -e ".[dev]"
```

Create a local `.env` from the repository `.env.example` and configure at least:

- `DATABASE_URL`;
- `JWT_SECRET` for any shared/non-development deployment.

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

Run the API:

```bash
uvicorn app.main:app --reload
```

Run tests:

```bash
pytest
```

## Health semantics

- `/health` answers whether the API process is alive.
- `/health/ready` performs a real database query and returns 503 when the database is unavailable.

## Database rule

PostgreSQL remains the production target. SQLite in tests is an isolated test dependency.

Schema changes must use Alembic migrations. Runtime code must not silently recreate or mutate the production schema.

## Authentication rule

There is no public registration route. Prototype users are provisioned administratively.

The default development JWT secret is rejected outside development/test.

## Audit rule

Inspection create/update/submit events are inserted in the same transaction as the state change. There is no audit update/delete API.

## Lifecycle rule

The API currently supports `draft -> pending_review`.

There is deliberately no finalize endpoint yet. Finalization will be introduced only when the officer-review/report phase has the data required to make it meaningful.
