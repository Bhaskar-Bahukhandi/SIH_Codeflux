import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.restoreAllMocks();
});

describe("dashboard integration path", () => {
  it("signs in, loads the persisted register, and opens inspection evidence detail", async () => {
    const inspection = {
      id: "inspection-e2e-1",
      product_name: "Packaged Flour",
      product_identifier: "FLOUR-01",
      officer_id: "officer-1",
      status: "pending_review",
      submitted_at: "2026-09-24T00:10:00Z",
      reopened_for_recheck_at: null,
      created_at: "2026-09-23T23:50:00Z",
      updated_at: "2026-09-24T00:10:00Z",
    };

    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);

      if (url === "/api/v1/auth/login") {
        expect(init?.method).toBe("POST");
        return jsonResponse({
          access_token: "integration-token",
          token_type: "bearer",
          expires_in: 3600,
        });
      }

      if (url === "/api/v1/auth/me") {
        return jsonResponse({
          id: "supervisor-1",
          full_name: "Supervisor Integration",
          email: "supervisor@example.test",
          role: "supervisor",
          is_active: true,
        });
      }

      if (url === "/api/v1/inspections") {
        return jsonResponse([inspection]);
      }

      if (url === "/api/v1/inspections/inspection-e2e-1") {
        return jsonResponse(inspection);
      }

      if (url === "/api/v1/inspections/inspection-e2e-1/captures") {
        return jsonResponse([]);
      }

      if (url === "/api/v1/inspections/inspection-e2e-1/rule-reviews") {
        return jsonResponse({ reviews: [], latest_by_rule_result: {} });
      }

      if (
        url === "/api/v1/inspections/inspection-e2e-1/declarations/latest" ||
        url === "/api/v1/inspections/inspection-e2e-1/rule-evaluations/latest" ||
        url === "/api/v1/inspections/inspection-e2e-1/finalization"
      ) {
        return jsonResponse(
          { error: { code: "not_found", message: "Not found." } },
          404,
        );
      }

      throw new Error(`Unexpected request in integration test: ${url}`);
    });

    render(<App />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "supervisor@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      await screen.findByRole("button", { name: "Open inspection Packaged Flour" }),
    ).toBeInTheDocument();

    expect(screen.getByLabelText("Operational inspection status summary")).toHaveTextContent(
      "Pending review1",
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Open inspection Packaged Flour" }),
    );

    const heading = await screen.findByRole("heading", { name: "Packaged Flour" });
    expect(heading).toBeInTheDocument();
    expect(screen.getByText("FLOUR-01")).toBeInTheDocument();
    expect(screen.getByText("No package-image evidence is persisted for this inspection.")).toBeInTheDocument();
    expect(screen.getByText("No declaration extraction exists yet.")).toBeInTheDocument();
    expect(screen.getByText("No preliminary rule evaluation exists yet.")).toBeInTheDocument();
    expect(screen.getByText("This inspection has not been finalized.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "← Inspection register" })).toBeInTheDocument();

    const inspectionListCall = fetchMock.mock.calls.find(([url]) => String(url) === "/api/v1/inspections");
    const detailCall = fetchMock.mock.calls.find(([url]) => String(url) === "/api/v1/inspections/inspection-e2e-1");
    expect(inspectionListCall).toBeDefined();
    expect(detailCall).toBeDefined();
    expect(new Headers(detailCall?.[1]?.headers).get("Authorization")).toBe(
      "Bearer integration-token",
    );
  });
});
