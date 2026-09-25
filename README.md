# CODEFLUX

**Smart India Hackathon 2026 - SIH26034**

CODEFLUX is our team's inspection-assistance prototype for checking packaged commodities under the Legal Metrology (Packaged Commodities) Rules, 2011.

The goal is simple: help an enforcement officer capture package evidence, extract the important declarations, run preliminary rule checks, review the findings, and keep a digital inspection record. The officer remains the final decision-maker.

## What the working prototype includes

- Flutter Officer app with product details and multi-image package capture.
- Offline SQLite drafts, local image storage, retry/reconnect sync and conflict-safe replay.
- Image quality checks and perspective correction with OpenCV.
- PaddleOCR-based package text extraction.
- Multi-image declaration fusion for **MRP** and **net quantity**.
- Versioned preliminary Legal Metrology checks backed by the rule-pack JSON in this repository.
- Officer review, correction and finalization flow.
- Evidence-backed PDF inspection reports for finalized inspections.
- React Supervisor dashboard with login, inspection history, search, status filters, evidence details and report download.
- FastAPI backend with PostgreSQL, authentication, role-based access and audit records.

## Current scope

This is an SIH prototype, not a complete Legal Metrology automation platform.

The current structured declaration/rule coverage is intentionally limited to MRP and net quantity for the supported retail-package profile. The mobile app supports Officer acceptance/correction and finalization for resolvable results. A full mobile recheck-and-resubmission cycle is not claimed as completed. Broader fields such as manufacturer/importer details, date declarations, consumer-care information, physical font-size measurement and automated misleading-label detection are also outside the current prototype scope.

## Technology

- **Mobile:** Flutter
- **Dashboard:** React + Vite
- **Backend:** Python + FastAPI
- **Computer Vision:** OpenCV
- **OCR:** PaddleOCR / PP-OCRv5
- **Central Database:** PostgreSQL
- **Offline Storage:** SQLite + local files

## Repository structure

```text
apps/
  mobile/       Officer field application
  dashboard/    Supervisor web application

services/
  api/          FastAPI backend and database migrations

packages/
  rulepacks/    Versioned Legal Metrology rule data

scripts/
  setup_mobile.ps1
  prefetch_ocr_models.py

Dockerfile
README.md
```

## Run the backend and dashboard

The Docker image builds the React dashboard and serves it from the FastAPI service.

```bash
docker build -t codeflux .
docker run --env-file .env -p 8000:8000 codeflux
```

Copy `.env.example` to `.env` and set a real PostgreSQL connection and a strong `JWT_SECRET` before running outside local development.

## Run the mobile app

The repository keeps platform scaffolding out of source control. Generate it locally first:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_mobile.ps1
```

Then run the app against the API:

```bash
flutter run --dart-define=CODEFLUX_API_URL=https://your-api.example/
```

## Team note

We are keeping this repository focused on the working product. Generated evidence, test datasets, validation reports and temporary demo files should stay outside the main source tree.
