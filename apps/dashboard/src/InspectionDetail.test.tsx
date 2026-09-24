import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import InspectionDetail from "./InspectionDetail";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("inspection detail", () => {
  it("loads persisted evidence and tolerates missing optional latest artifacts", async () => {
    const inspection = {
      id: "inspection-1",
      product_name: "Sample Biscuit Pack",
      product_identifier: "DEMO-001",
      officer_id: "officer-1",
      status: "pending_review",
      submitted_at: "2026-09-23T10:00:00Z",
      reopened_for_recheck_at: null,
      created_at: "2026-09-23T09:00:00Z",
      updated_at: "2026-09-23T10:00:00Z",
    };
    const capture = {
      id: "capture-1",
      inspection_id: "inspection-1",
      uploader_user_id: "officer-1",
      view_type: "front",
      original_filename: "front.jpg",
      sha256: "abc123",
      mime_type: "image/jpeg",
      size_bytes: 1024,
      width_px: 1000,
      height_px: 800,
      created_at: "2026-09-23T09:10:00Z",
    };

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/inspections/inspection-1")) return jsonResponse(inspection);
      if (url.endsWith("/inspections/inspection-1/captures")) return jsonResponse([capture]);
      if (url.endsWith("/inspections/inspection-1/rule-reviews")) {
        return jsonResponse({ reviews: [], latest_by_rule_result: {} });
      }
      return jsonResponse({ error: { code: "not_found", message: "Not found." } }, 404);
    });

    render(
      <InspectionDetail
        inspectionId="inspection-1"
        accessToken="token"
        onBack={() => undefined}
        onUnauthorized={() => undefined}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Sample Biscuit Pack" })).toBeInTheDocument();
    expect(screen.getByText("front.jpg")).toBeInTheDocument();
    expect(screen.getAllByText("Not available").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("No declaration extraction exists yet.")).toBeInTheDocument();
    expect(screen.getByText("No preliminary rule evaluation exists yet.")).toBeInTheDocument();
    expect(screen.getByText("This inspection has not been finalized.")).toBeInTheDocument();
  });

  it("surfaces finalized report metadata and download control", async () => {
    const inspection = {
      id: "inspection-2",
      product_name: "Cooking Oil Bottle",
      product_identifier: "OIL-7",
      officer_id: "officer-2",
      status: "finalized",
      submitted_at: "2026-09-22T10:00:00Z",
      reopened_for_recheck_at: null,
      created_at: "2026-09-22T09:00:00Z",
      updated_at: "2026-09-22T12:00:00Z",
    };
    const finalization = {
      id: "finalization-1",
      inspection_id: "inspection-2",
      finalized_by_user_id: "officer-2",
      rule_evaluation_run_id: "rule-run-1",
      rule_pack_id: "lmpc-retail-evidence-v1",
      rule_pack_version: "1.0.0",
      rule_pack_sha256: "rulehash",
      snapshot: {},
      snapshot_sha256: "snap",
      report_id: "report-1",
      report_version: "1",
      report_sha256: "reporthash",
      report_size_bytes: 2048,
      finalized_at: "2026-09-22T12:00:00Z",
    };

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/inspections/inspection-2")) return jsonResponse(inspection);
      if (url.endsWith("/inspections/inspection-2/captures")) return jsonResponse([]);
      if (url.endsWith("/inspections/inspection-2/rule-reviews")) {
        return jsonResponse({ reviews: [], latest_by_rule_result: {} });
      }
      if (url.endsWith("/inspections/inspection-2/finalization")) return jsonResponse(finalization);
      return jsonResponse({ error: { code: "not_found", message: "Not found." } }, 404);
    });

    render(
      <InspectionDetail
        inspectionId="inspection-2"
        accessToken="token"
        onBack={() => undefined}
        onUnauthorized={() => undefined}
      />,
    );

    expect(await screen.findByText("report-1")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Download evidence-backed PDF" }),
    ).toBeInTheDocument();
  });
});
