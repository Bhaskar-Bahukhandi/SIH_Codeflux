# ADR 0001 — Technical Baseline

Status: Accepted for foundation  
Date: 2026-09-22

## Context

The submitted SIH proposal lists Flutter and React for client interfaces, Python with FastAPI/Flask for backend work, OpenCV and PaddleOCR for vision/OCR, PostgreSQL centrally, and SQLite locally.

Using multiple interchangeable server frameworks during the prototype would add complexity without improving the proposed workflow.

## Decision

Use:

- Flutter for the field/mobile application;
- React for the supervisor/admin dashboard;
- Python + FastAPI for the backend API;
- OpenCV + PaddleOCR for image/OCR work;
- PostgreSQL for central persistent data;
- SQLite + local file storage for offline field data.

## Consequences

- The repository can be separated by application/service responsibility.
- API contracts can remain independent of UI implementation.
- Offline storage remains a first-class requirement.
- This decision does not freeze hosting, authentication provider, object-storage vendor, or exact on-device/server processing split.

## Reversal

If a baseline choice becomes technically unsuitable, replace it only through a new ADR that records evidence, migration impact, fallback plan, and validation.
