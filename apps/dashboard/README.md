# Web Dashboard

Technology: React + TypeScript.

## Phase 8A scope

The first dashboard slice is intentionally limited to:

- Supervisor/Admin sign-in using the existing CODEFLUX authentication API;
- browser session persistence for the prototype using session storage and server-provided expiry;
- persisted inspection list from the backend;
- deterministic product/identifier/inspection-ID search;
- inspection-status filtering;
- explicit loading, empty, filter-empty and error states;
- real API data only.

The dashboard does not present static/demo statistics as live operational data and does not duplicate Legal Metrology rule logic.

Inspection evidence/detail views, Officer review details, finalization/report retrieval and dashboard monitoring polish remain later Phase 8 slices.

## Authorization boundary

The dashboard verifies the authenticated identity through `GET /api/v1/auth/me` and only opens the UI for `supervisor` or `admin` roles.

This client-side role gate is a presentation boundary, not a replacement for backend authorization. API endpoints remain authoritative.

## API configuration

The browser client uses the same-origin `/api` path. During local development, Vite proxies that path to the CODEFLUX API target.

Set `CODEFLUX_API_TARGET` when the API is not running at the local development default:

```bash
CODEFLUX_API_TARGET=http://127.0.0.1:8000 npm run dev
```

No production or demo server address is hard-coded into application source.

## Local validation

From `apps/dashboard`:

```bash
npm install
npm test
npm run build
```

Phase 8A is not complete unless dashboard tests/build and the existing API regression suite pass in GitHub Actions.
