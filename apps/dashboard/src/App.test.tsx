import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const supervisor = {
  id: "user-1",
  full_name: "Supervisor Test",
  email: "supervisor@example.test",
  role: "supervisor",
  is_active: true,
};

const inspections = [
  {
    id: "11111111-1111-1111-1111-111111111111",
    product_name: "Sample Biscuit Pack",
    product_identifier: "DEMO-001",
    officer_id: "officer-1",
    status: "pending_review",
    submitted_at: "2026-09-23T10:00:00Z",
    reopened_for_recheck_at: null,
    created_at: "2026-09-23T09:00:00Z",
    updated_at: "2026-09-23T10:00:00Z",
  },
  {
    id: "22222222-2222-2222-2222-222222222222",
    product_name: "Cooking Oil Bottle",
    product_identifier: "OIL-7",
    officer_id: "officer-2",
    status: "finalized",
    submitted_at: "2026-09-22T10:00:00Z",
    reopened_for_recheck_at: null,
    created_at: "2026-09-22T09:00:00Z",
    updated_at: "2026-09-22T12:00:00Z",
  },
];

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("dashboard authentication and inspection register", () => {
  it("authenticates a supervisor and loads persisted inspections", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        jsonResponse({ access_token: "token-1", token_type: "bearer", expires_in: 3600 }),
      )
      .mockResolvedValueOnce(jsonResponse(supervisor))
      .mockResolvedValueOnce(jsonResponse(inspections));

    render(<App />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "supervisor@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Sample Biscuit Pack")).toBeInTheDocument();
    expect(screen.getByText("Cooking Oil Bottle")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/v1/inspections");
    const inspectionHeaders = new Headers(fetchMock.mock.calls[2]?.[1]?.headers);
    expect(inspectionHeaders.get("Authorization")).toBe("Bearer token-1");
  });

  it("rejects an officer account before loading dashboard records", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        jsonResponse({ access_token: "token-2", token_type: "bearer", expires_in: 3600 }),
      )
      .mockResolvedValueOnce(jsonResponse({ ...supervisor, role: "officer" }));

    render(<App />);
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "officer@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      await screen.findByText("This dashboard is limited to Supervisor and Admin accounts."),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("filters deterministically by text and status", async () => {
    sessionStorage.setItem(
      "codeflux.dashboard.session.v1",
      JSON.stringify({
        accessToken: "token-3",
        expiresAt: Date.now() + 60_000,
        user: supervisor,
      }),
    );
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(jsonResponse(inspections));

    render(<App />);
    expect(await screen.findByText("Sample Biscuit Pack")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "oil-7" } });
    expect(screen.queryByText("Sample Biscuit Pack")).not.toBeInTheDocument();
    expect(screen.getByText("Cooking Oil Bottle")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "pending_review" } });

    const body = screen.getByRole("table").querySelector("tbody");
    expect(body).not.toBeNull();
    expect(within(body as HTMLElement).getByText("Sample Biscuit Pack")).toBeInTheDocument();
    expect(within(body as HTMLElement).queryByText("Cooking Oil Bottle")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("1 of 2 shown")).toBeInTheDocument());
  });
});
