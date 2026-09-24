# Web Dashboard

Technology: React + TypeScript.

## Phase 8 scope implemented so far

### 8A — foundation, authentication and inspection register

- Supervisor/Admin sign-in using the existing CODEFLUX authentication API;
- browser session persistence for the prototype using session storage and server-provided expiry;
- persisted inspection list;
- deterministic product/identifier/inspection-ID search;
- inspection-status filtering;
- explicit loading, empty, filter-empty and error states.

### 8B — inspection evidence detail

The current branch adds read-oriented inspection detail using existing persisted backend data:

- inspection metadata;
- package-capture metadata;
- latest quality, geometry and OCR state per capture;
- OCR text evidence;
- latest declaration fusion summaries;
- latest preliminary rule-evaluation results;
- latest Officer review decision for each rule result;
- finalization metadata;
- authenticated evidence-backed PDF report download when finalized.

Missing latest quality/geometry/OCR/declaration/rule/finalization records are treated as absent evidence, not invented state.

## Safety and authorization boundaries

The dashboard verifies identity through `GET /api/v1/auth/me` and only opens for `supervisor` or `admin` roles.

Client-side role gating is a presentation boundary, not a replacement for backend authorization. API endpoints remain authoritative.

The dashboard:

- does not present static/demo statistics as live operational data;
- does not duplicate Legal Metrology rule logic;
- does not create Supervisor overrides;
- does not convert missing OCR/declaration evidence into a violation;
- does not expose penalty or statutory notice workflows.

## API configuration

The browser client uses the same-origin `/api` path. During local development, Vite proxies that path to the CODEFLUX API target.

Set `CODEFLUX_API_TARGET` when the API is not running at the local development default:

```bash
CODEFLUX_API_TARGET=http://127.0.0.1:8000 npm run dev
```

## Local validation

From `apps/dashboard`:

```bash
npm install
npm test
npm run build
```

Dashboard changes are also gated by the existing API migration chain and regression suite in GitHub Actions.
