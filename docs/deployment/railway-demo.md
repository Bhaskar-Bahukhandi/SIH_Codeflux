# SIH Demo Deployment Decision

Issue: #43

Status: repository deployment contract validated; live Railway provisioning pending

## Decision

Use **Railway Hobby** as the initial SIH demo hosting target for the combined CODEFLUX web/API service, with a Railway PostgreSQL service and a persistent volume for captured evidence.

This is a demo-deployment decision, not a production-readiness certification.

## Why Railway for this prototype

The current repository needs:

- a long-running Python/FastAPI service;
- CPU/RAM headroom for PP-OCRv5;
- PostgreSQL;
- persistent arbitrary-file storage for image/report evidence;
- a public HTTPS endpoint;
- GitHub/Docker deployment;
- a simple monorepo workflow.

Railway currently supports Dockerfile deployments, Postgres, persistent volumes, health checks and GitHub-connected services. Its Free plan is limited to 0.5 GB RAM after trial and is therefore not the approved validation target for the CPU OCR service. Hobby provides usage-based compute with higher resource limits and up to 5 GB volume storage.

Primary platform references:

- https://railway.com/pricing
- https://docs.railway.com/builds/dockerfiles
- https://docs.railway.com/databases/postgresql
- https://docs.railway.com/volumes/reference
- https://docs.railway.com/deployments/monorepo

## Repository deployment shape

The root `Dockerfile` builds one public service:

1. Vite builds the Supervisor dashboard.
2. Python installs the FastAPI API plus the pinned OCR runtime.
3. PP-OCRv5 model artifacts are prefetched during image construction.
4. The dashboard build is copied into the API image.
5. FastAPI serves API/health routes and the dashboard from the same origin.
6. Container startup applies Alembic migrations before starting uvicorn.

Local Vite development is unchanged. The dashboard is served by FastAPI only when `DASHBOARD_ROOT` is configured and contains `index.html`.

## Railway project layout

Create exactly these runtime resources:

- `codeflux-demo`: GitHub-backed service using the repository root Dockerfile;
- `Postgres`: Railway PostgreSQL service;
- one persistent volume attached to `codeflux-demo` at `/data`.

Do not expose PostgreSQL publicly for the SIH demo. The app and database should communicate through Railway private networking.

## Required service variables

Configure the `codeflux-demo` service with:

```text
APP_ENV=demo
JWT_SECRET=<strong random secret, at least 32 characters>
DATABASE_URL=${{Postgres.DATABASE_URL}}
MEDIA_ROOT=/data/media
OCR_INFERENCE_ENGINE=paddle
OCR_LANGUAGE=en
OCR_MODEL_VERSION=PP-OCRv5
OCR_DEVICE=cpu
OCR_MIN_CONFIDENCE=0.0
OCR_ENABLE_MKLDNN=false
PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
```

The API normalizes standard `postgres://` / `postgresql://` URLs to the installed SQLAlchemy `psycopg` driver.

Do not commit the real JWT secret or generated Railway credentials.

## Railway service settings

Use:

- source: this GitHub repository;
- root directory: repository root;
- Dockerfile: root `Dockerfile` (auto-detected);
- public networking: enabled for the app service;
- health check path: `/health/ready`;
- replicas: 1 for the SIH demo;
- volume mount path: `/data`.

A single replica is intentional because captured evidence currently uses a local persistent filesystem. Horizontal scaling would require shared object storage or another explicitly designed media backend.

## First deployment verification

Do not consider the demo deployment valid until all of the following are observed on the live Railway URL:

1. `GET /health` returns `{"status":"ok"}`.
2. `GET /health/ready` returns `{"status":"ready"}`.
3. `GET /` loads the real CODEFLUX Supervisor dashboard.
4. Supervisor/Admin login works with a deliberately provisioned account.
5. A real mobile client can point `CODEFLUX_API_URL` at the HTTPS domain.
6. One package capture reaches preprocessing, OCR, extraction and preliminary rule evaluation.
7. The uploaded evidence remains retrievable after an app-service redeploy/restart.
8. The database record remains present after redeploy/restart.
9. No credentials or test/demo secrets appear in repository files or public logs.

## Repository validation result

The dedicated SIH Demo Container workflow passed on this deployment contract. The executed image:

- built successfully with the React dashboard, API and prefetched PP-OCRv5 artifacts;
- applied Alembic migrations at startup;
- reached `/health/ready`;
- served the real dashboard from `/`;
- kept API/health routes available on the same origin;
- contained PaddleOCR 3.7.0 and PaddlePaddle 3.2.2.

The full API regression suite on the same PR contains 145 passing tests.

## Evidence boundaries

The green repository container smoke test proves:

- the combined image builds;
- Alembic migrations execute in the image;
- FastAPI becomes database-ready;
- the static dashboard is served from the same origin;
- pinned PaddleOCR/PaddlePaddle packages are present;
- PP-OCRv5 model initialization succeeded during image build.

It does not prove:

- Railway account configuration is correct;
- the paid resource size is sufficient under real demo load;
- physical-device behavior;
- real-package OCR/extraction accuracy;
- production security/SLA suitability.

Those require the corresponding live/external evidence.

## Rollback

The deployment work must remain reversible:

- local Vite development still works;
- server PP-OCRv5 remains the authoritative OCR path;
- no Railway-specific SDK is introduced into application code;
- removing `DASHBOARD_ROOT` returns FastAPI to API-only behavior;
- the platform can be changed later without changing Legal Metrology semantics.
