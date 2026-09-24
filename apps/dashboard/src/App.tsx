import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, getCurrentUser, listInspections, login } from "./api";
import InspectionDetail from "./InspectionDetail";
import {
  clearSession,
  loadSession,
  saveSession,
  type DashboardSession,
} from "./session";
import type { Inspection, InspectionStatus } from "./types";
import "./styles.css";

type LoadState = "idle" | "loading" | "ready" | "error";
type StatusFilter = "all" | InspectionStatus;

const statusLabels: Record<InspectionStatus, string> = {
  draft: "Draft",
  pending_review: "Pending review",
  finalized: "Finalized",
};

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Unknown";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "An unexpected error occurred.";
}

export default function App() {
  const [session, setSession] = useState<DashboardSession | null>(() => loadSession());
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadError, setLoadError] = useState("");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [selectedInspectionId, setSelectedInspectionId] = useState<string | null>(null);

  const expireSession = useCallback(() => {
    clearSession();
    setSession(null);
    setSelectedInspectionId(null);
    setLoadError("Your session expired. Sign in again.");
    setLoadState("idle");
  }, []);

  useEffect(() => {
    if (!session) {
      setInspections([]);
      setLoadState("idle");
      return;
    }

    let active = true;
    setLoadState("loading");
    setLoadError("");

    listInspections(session.accessToken)
      .then((records) => {
        if (!active) return;
        setInspections(records);
        setLoadState("ready");
      })
      .catch((error: unknown) => {
        if (!active) return;
        if (error instanceof ApiError && error.status === 401) {
          expireSession();
          return;
        }
        setLoadError(errorMessage(error));
        setLoadState("error");
      });

    return () => {
      active = false;
    };
  }, [expireSession, session]);

  const visibleInspections = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return inspections.filter((inspection) => {
      if (statusFilter !== "all" && inspection.status !== statusFilter) return false;
      if (!normalizedQuery) return true;

      const searchable = [
        inspection.product_name,
        inspection.product_identifier ?? "",
        inspection.id,
      ]
        .join("\n")
        .toLowerCase();
      return searchable.includes(normalizedQuery);
    });
  }, [inspections, query, statusFilter]);

  const statusSummary = useMemo(
    () => ({
      total: inspections.length,
      draft: inspections.filter((inspection) => inspection.status === "draft").length,
      pendingReview: inspections.filter(
        (inspection) => inspection.status === "pending_review",
      ).length,
      finalized: inspections.filter(
        (inspection) => inspection.status === "finalized",
      ).length,
    }),
    [inspections],
  );

  function handleAuthenticated(nextSession: DashboardSession) {
    saveSession(nextSession);
    setSession(nextSession);
    setQuery("");
    setStatusFilter("all");
    setSelectedInspectionId(null);
  }

  function signOut() {
    clearSession();
    setSession(null);
    setInspections([]);
    setQuery("");
    setStatusFilter("all");
    setSelectedInspectionId(null);
    setLoadError("");
  }

  if (!session) {
    return <LoginScreen onAuthenticated={handleAuthenticated} notice={loadError} />;
  }

  return (
    <main className="shell">
      <a className="skip-link" href="#dashboard-content">
        Skip to dashboard content
      </a>
      <header className="topbar">
        <div>
          <p className="eyebrow">SIH 2026 · SIH26034</p>
          <h1>CODEFLUX</h1>
          <p className="subtitle">Supervisor inspection register</p>
        </div>
        <div className="account">
          <div>
            <strong>{session.user.full_name}</strong>
            <span>{session.user.role === "admin" ? "Admin" : "Supervisor"}</span>
          </div>
          <button className="secondary-button" type="button" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>

      <div id="dashboard-content">
      {selectedInspectionId ? (
        <InspectionDetail
          inspectionId={selectedInspectionId}
          accessToken={session.accessToken}
          onBack={() => setSelectedInspectionId(null)}
          onUnauthorized={expireSession}
        />
      ) : (
        <section className="register" aria-labelledby="inspection-heading">
          <div className="register-heading">
            <div>
              <p className="section-kicker">Persisted backend records</p>
              <h2 id="inspection-heading">Inspections</h2>
            </div>
            {loadState === "ready" && (
              <p className="record-count" aria-live="polite">
                {visibleInspections.length} of {inspections.length} shown
              </p>
            )}
          </div>

          {loadState === "ready" && (
            <dl className="status-summary" aria-label="Operational inspection status summary">
              <div><dt>Total</dt><dd>{statusSummary.total}</dd></div>
              <div><dt>Draft</dt><dd>{statusSummary.draft}</dd></div>
              <div><dt>Pending review</dt><dd>{statusSummary.pendingReview}</dd></div>
              <div><dt>Finalized</dt><dd>{statusSummary.finalized}</dd></div>
            </dl>
          )}

          <div className="filters" aria-label="Inspection filters">
            <label>
              <span>Search</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Product, identifier, or inspection ID"
              />
            </label>
            <label>
              <span>Status</span>
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
              >
                <option value="all">All statuses</option>
                <option value="draft">Draft</option>
                <option value="pending_review">Pending review</option>
                <option value="finalized">Finalized</option>
              </select>
            </label>
          </div>

          {loadState === "loading" && (
            <div className="state-panel" role="status">
              Loading persisted inspections…
            </div>
          )}

          {loadState === "error" && (
            <div className="state-panel error-panel" role="alert">
              <strong>Could not load inspections.</strong>
              <p>{loadError}</p>
              <button
                className="secondary-button"
                type="button"
                onClick={() => setSession({ ...session })}
              >
                Retry
              </button>
            </div>
          )}

          {loadState === "ready" && inspections.length === 0 && (
            <div className="state-panel">
              <strong>No persisted inspections yet.</strong>
              <p>New field records will appear here after they are synchronized to the API.</p>
            </div>
          )}

          {loadState === "ready" && inspections.length > 0 && visibleInspections.length === 0 && (
            <div className="state-panel">
              <strong>No inspections match these filters.</strong>
              <p>Clear the search text or choose another status.</p>
            </div>
          )}

          {loadState === "ready" && visibleInspections.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Product</th>
                    <th scope="col">Identifier</th>
                    <th scope="col">Status</th>
                    <th scope="col">Created</th>
                    <th scope="col">Inspection ID</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleInspections.map((inspection) => (
                    <tr key={inspection.id}>
                      <td className="product-cell">
                        <button
                          className="inspection-link"
                          type="button"
                          onClick={() => setSelectedInspectionId(inspection.id)}
                          aria-label={`Open inspection ${inspection.product_name}`}
                        >
                          {inspection.product_name}
                        </button>
                      </td>
                      <td>{inspection.product_identifier ?? "—"}</td>
                      <td>
                        <span className={`status status-${inspection.status}`}>
                          {statusLabels[inspection.status]}
                        </span>
                      </td>
                      <td>{formatDate(inspection.created_at)}</td>
                      <td className="id-cell">{inspection.id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
      </div>

      <footer>
        Dashboard records come from persisted CODEFLUX API data. Legal evaluation semantics remain on the backend.
      </footer>
    </main>
  );
}

function LoginScreen({
  onAuthenticated,
  notice,
}: {
  onAuthenticated: (session: DashboardSession) => void;
  notice: string;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      const token = await login(email.trim(), password);
      const user = await getCurrentUser(token.access_token);
      if (user.role !== "supervisor" && user.role !== "admin") {
        throw new Error("This dashboard is limited to Supervisor and Admin accounts.");
      }

      onAuthenticated({
        accessToken: token.access_token,
        expiresAt: Date.now() + token.expires_in * 1000,
        user,
      });
    } catch (caught: unknown) {
      setError(errorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-panel" aria-labelledby="login-heading">
        <div className="login-intro">
          <p className="eyebrow">Smart India Hackathon 2026</p>
          <h1 id="login-heading">CODEFLUX</h1>
          <p>
            Supervisor workspace for persisted Legal Metrology inspection records.
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <label>
            <span>Email</span>
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label>
            <span>Password</span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>

          {(error || notice) && (
            <div className="form-error" role="alert">
              {error || notice}
            </div>
          )}

          <button className="primary-button" type="submit" disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="login-note">
          Access is verified against the existing CODEFLUX API. No demo credentials or static inspection data are embedded in this client.
        </p>
      </section>
    </main>
  );
}
