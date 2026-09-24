import { useEffect, useState } from "react";

import {
  ApiError,
  getFinalization,
  getFinalizedReport,
  getInspection,
  getLatestDeclarations,
  getLatestGeometry,
  getLatestOcr,
  getLatestQuality,
  getLatestRuleEvaluation,
  getRuleReviews,
  listCaptures,
} from "./api";
import type { InspectionDetailState } from "./types";

type DetailLoadState = "loading" | "ready" | "error";

function formatDate(value: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Unknown";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function prettyValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function readableStatus(value: string): string {
  return value.replaceAll("_", " ");
}

export default function InspectionDetail({
  inspectionId,
  accessToken,
  onBack,
  onUnauthorized,
}: {
  inspectionId: string;
  accessToken: string;
  onBack: () => void;
  onUnauthorized: () => void;
}) {
  const [state, setState] = useState<DetailLoadState>("loading");
  const [detail, setDetail] = useState<InspectionDetailState | null>(null);
  const [error, setError] = useState("");
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState("");

  useEffect(() => {
    let active = true;
    setState("loading");
    setError("");

    async function load() {
      try {
        const [inspection, captures, declarations, ruleEvaluation, reviews, finalization] =
          await Promise.all([
            getInspection(inspectionId, accessToken),
            listCaptures(inspectionId, accessToken),
            getLatestDeclarations(inspectionId, accessToken),
            getLatestRuleEvaluation(inspectionId, accessToken),
            getRuleReviews(inspectionId, accessToken),
            getFinalization(inspectionId, accessToken),
          ]);

        const captureEvidence = await Promise.all(
          captures.map(async (capture) => {
            const [quality, geometry, ocr] = await Promise.all([
              getLatestQuality(inspectionId, capture.id, accessToken),
              getLatestGeometry(inspectionId, capture.id, accessToken),
              getLatestOcr(inspectionId, capture.id, accessToken),
            ]);
            return { capture, quality, geometry, ocr };
          }),
        );

        if (!active) return;
        setDetail({
          inspection,
          captures: captureEvidence,
          declarations,
          ruleEvaluation,
          reviews,
          finalization,
        });
        setState("ready");
      } catch (caught: unknown) {
        if (!active) return;
        if (caught instanceof ApiError && caught.status === 401) {
          onUnauthorized();
          return;
        }
        setError(caught instanceof Error ? caught.message : "Could not load inspection detail.");
        setState("error");
      }
    }

    void load();
    return () => {
      active = false;
    };
  }, [accessToken, inspectionId, onUnauthorized]);

  async function downloadReport() {
    if (!detail?.finalization) return;
    setReportBusy(true);
    setReportError("");
    try {
      const { blob, filename } = await getFinalizedReport(inspectionId, accessToken);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (caught: unknown) {
      if (caught instanceof ApiError && caught.status === 401) {
        onUnauthorized();
        return;
      }
      setReportError(caught instanceof Error ? caught.message : "Report download failed.");
    } finally {
      setReportBusy(false);
    }
  }

  return (
    <section className="detail-view" aria-labelledby="detail-heading">
      <button className="back-button" type="button" onClick={onBack}>
        ← Inspection register
      </button>

      {state === "loading" && (
        <div className="state-panel" role="status">
          Loading inspection evidence…
        </div>
      )}

      {state === "error" && (
        <div className="state-panel error-panel" role="alert">
          <strong>Could not load inspection detail.</strong>
          <p>{error}</p>
        </div>
      )}

      {state === "ready" && detail && (
        <>
          <header className="detail-header">
            <div>
              <p className="section-kicker">Inspection evidence</p>
              <h2 id="detail-heading">{detail.inspection.product_name}</h2>
              <p className="detail-identifier">
                {detail.inspection.product_identifier ?? "No product identifier"}
              </p>
            </div>
            <span className={`status status-${detail.inspection.status}`}>
              {readableStatus(detail.inspection.status)}
            </span>
          </header>

          <dl className="metadata-grid">
            <div><dt>Inspection ID</dt><dd>{detail.inspection.id}</dd></div>
            <div><dt>Officer ID</dt><dd>{detail.inspection.officer_id ?? "—"}</dd></div>
            <div><dt>Created</dt><dd>{formatDate(detail.inspection.created_at)}</dd></div>
            <div><dt>Submitted</dt><dd>{formatDate(detail.inspection.submitted_at)}</dd></div>
            <div><dt>Reopened for recheck</dt><dd>{formatDate(detail.inspection.reopened_for_recheck_at)}</dd></div>
            <div><dt>Last updated</dt><dd>{formatDate(detail.inspection.updated_at)}</dd></div>
          </dl>

          <section className="detail-section">
            <div className="section-heading-row">
              <div>
                <p className="section-kicker">Package evidence</p>
                <h3>Captures</h3>
              </div>
              <span>{detail.captures.length} capture{detail.captures.length === 1 ? "" : "s"}</span>
            </div>

            {detail.captures.length === 0 ? (
              <p className="muted-copy">No package-image evidence is persisted for this inspection.</p>
            ) : (
              <div className="capture-list">
                {detail.captures.map(({ capture, quality, geometry, ocr }) => (
                  <article className="capture-card" key={capture.id}>
                    <div className="capture-title">
                      <div>
                        <strong>{readableStatus(capture.view_type)}</strong>
                        <span>{capture.original_filename ?? capture.id}</span>
                      </div>
                      <span>{capture.width_px} × {capture.height_px}</span>
                    </div>
                    <dl className="compact-grid">
                      <div><dt>Quality</dt><dd>{quality ? readableStatus(quality.status) : "Not available"}</dd></div>
                      <div><dt>Geometry</dt><dd>{geometry ? readableStatus(geometry.status) : "Not available"}</dd></div>
                      <div><dt>OCR blocks</dt><dd>{ocr ? ocr.run.block_count : "Not available"}</dd></div>
                      <div><dt>SHA-256</dt><dd className="hash-value">{capture.sha256}</dd></div>
                    </dl>
                    {quality?.reasons.length ? (
                      <p className="evidence-note">Quality notes: {quality.reasons.join(", ")}</p>
                    ) : null}
                    {geometry?.reasons.length ? (
                      <p className="evidence-note">Geometry notes: {geometry.reasons.join(", ")}</p>
                    ) : null}
                    {ocr && ocr.blocks.length > 0 ? (
                      <details>
                        <summary>OCR text evidence</summary>
                        <ol className="ocr-list">
                          {ocr.blocks.map((block) => (
                            <li key={block.id}>
                              <span>{block.text}</span>
                              <small>{Math.round(block.confidence * 100)}%</small>
                            </li>
                          ))}
                        </ol>
                      </details>
                    ) : null}
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="detail-section">
            <p className="section-kicker">Declaration extraction</p>
            <h3>Latest declaration evidence</h3>
            {!detail.declarations ? (
              <p className="muted-copy">No declaration extraction exists yet.</p>
            ) : (
              <div className="evidence-table-wrap">
                <table className="evidence-table">
                  <thead>
                    <tr>
                      <th>Declaration</th>
                      <th>Fusion state</th>
                      <th>Canonical value</th>
                      <th>Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.declarations.summaries.map((summary) => (
                      <tr key={summary.id}>
                        <td>{readableStatus(summary.declaration_type)}</td>
                        <td>{readableStatus(summary.status)}</td>
                        <td>{prettyValue(summary.canonical_value)}</td>
                        <td>{summary.observation_count} observation(s), {summary.capture_count} capture(s)</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="detail-section">
            <p className="section-kicker">Preliminary checks</p>
            <h3>Latest rule evaluation</h3>
            {!detail.ruleEvaluation ? (
              <p className="muted-copy">No preliminary rule evaluation exists yet.</p>
            ) : (
              <>
                <p className="run-meta">
                  Rule pack {detail.ruleEvaluation.run.rule_pack_id} · version {detail.ruleEvaluation.run.rule_pack_version}
                </p>
                <div className="rule-list">
                  {detail.ruleEvaluation.results.map((result) => {
                    const latestReview = detail.reviews.latest_by_rule_result[result.id];
                    return (
                      <article className="rule-card" key={result.id}>
                        <div className="rule-card-heading">
                          <div>
                            <strong>{result.rule_id}</strong>
                            <span>{result.provision}</span>
                          </div>
                          <span className="status">{readableStatus(result.status)}</span>
                        </div>
                        <p>{result.explanation}</p>
                        <div className="review-state">
                          <span>Officer review</span>
                          <strong>{latestReview ? readableStatus(latestReview.decision) : "Not reviewed"}</strong>
                        </div>
                        {latestReview?.note ? <p className="evidence-note">{latestReview.note}</p> : null}
                      </article>
                    );
                  })}
                </div>
              </>
            )}
          </section>

          <section className="detail-section">
            <p className="section-kicker">Finalization</p>
            <h3>Report state</h3>
            {!detail.finalization ? (
              <p className="muted-copy">This inspection has not been finalized.</p>
            ) : (
              <div className="finalization-panel">
                <dl className="compact-grid">
                  <div><dt>Finalized</dt><dd>{formatDate(detail.finalization.finalized_at)}</dd></div>
                  <div><dt>Report version</dt><dd>{detail.finalization.report_version}</dd></div>
                  <div><dt>Report ID</dt><dd>{detail.finalization.report_id}</dd></div>
                  <div><dt>Size</dt><dd>{detail.finalization.report_size_bytes.toLocaleString()} bytes</dd></div>
                </dl>
                <button
                  className="primary-button report-button"
                  type="button"
                  disabled={reportBusy}
                  onClick={() => void downloadReport()}
                >
                  {reportBusy ? "Preparing report…" : "Download evidence-backed PDF"}
                </button>
                {reportError ? <p className="form-error" role="alert">{reportError}</p> : null}
              </div>
            )}
          </section>
        </>
      )}
    </section>
  );
}
