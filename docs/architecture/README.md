# Architecture Baseline

The architecture must remain aligned with the submitted SIH proposal.

## Selected baseline

| Layer | Baseline |
| --- | --- |
| Field application | Flutter |
| Web dashboard | React |
| Backend API | Python + FastAPI |
| Image processing | OpenCV |
| OCR | PaddleOCR |
| Central database | PostgreSQL |
| Offline local data | SQLite + local file storage |

## Core separation

The system should keep these responsibilities separable:

- capture and local inspection workflow;
- image preprocessing;
- OCR and declaration extraction;
- versioned rule evaluation;
- officer verification;
- reporting;
- synchronization;
- dashboard/read-side access.

UI code must not become the only location of legal or extraction logic.

## Core data traceability

A finding should eventually be traceable through:

`Inspection -> Capture/Image -> OCR Result -> Declaration -> Rule/Version -> Finding -> Officer Review -> Report`

Officer corrections must preserve the original machine output rather than silently overwrite it.

## Non-goals for the current SIH core

The current architecture does not require:

- manufacturer self-service portal;
- consumer scanner;
- e-commerce compliance API;
- blockchain;
- general legal RAG assistant;
- autonomous legal adjudication.

These remain optional future ideas.
