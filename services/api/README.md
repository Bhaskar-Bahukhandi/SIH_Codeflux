# Backend API

Technology: Python + FastAPI.

This service is the central API foundation for persisted inspection data.

## Current Phase 1 capabilities

- application factory;
- `GET /health`;
- SQLAlchemy database foundation;
- Alembic migrations;
- persisted users with Officer / Supervisor / Admin roles;
- Argon2 password hashing;
- JWT login and current-user endpoint;
- protected inspection API;
- officer ownership and read isolation;
- supervisor/admin inspection read access;
- draft inspection editing;
- `draft -> pending_review` submission;
- stable domain error responses;
- isolated API/persistence/auth tests.

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

## Database rule

PostgreSQL remains the production target. SQLite in tests is an isolated test dependency.

Schema changes must use Alembic migrations. Runtime code must not silently recreate or mutate the production schema.

## Authentication rule

There is no public registration route. Prototype users are provisioned administratively.

The default development JWT secret is rejected outside development/test. A deployment must provide a replacement secret.

## Lifecycle rule

The API currently supports `draft -> pending_review`.

There is deliberately no finalize endpoint yet. Finalization will be introduced only when the officer-review/report phase has the data required to make finalization meaningful.
