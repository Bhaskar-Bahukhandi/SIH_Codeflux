# Web Dashboard

Technology: React + TypeScript.

## Phase 8A scope

The first dashboard slice is intentionally limited to:

- Supervisor/Admin sign-in using the existing CODEFLUX authentication API;
- persisted inspection list from the backend;
- deterministic product/identifier search;
- inspection-status filtering;
- explicit loading, empty and error states;
- real API data only.

The dashboard must not present static/demo statistics as live operational data.

Inspection evidence/detail views, Officer review details, finalization/report retrieval and dashboard monitoring polish remain later Phase 8 slices.

## API configuration

The browser client uses a same-origin API path. During local development, Vite proxies that path to a configured CODEFLUX API target.

No production or demo server address is hard-coded into application source.
