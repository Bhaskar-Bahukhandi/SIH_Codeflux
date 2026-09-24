import type { CurrentUser } from "./types";

const STORAGE_KEY = "codeflux.dashboard.session.v1";

export interface DashboardSession {
  accessToken: string;
  expiresAt: number;
  user: CurrentUser;
}

export function saveSession(session: DashboardSession): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}

export function loadSession(now = Date.now()): DashboardSession | null {
  const raw = sessionStorage.getItem(STORAGE_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as Partial<DashboardSession>;
    if (
      typeof parsed.accessToken !== "string" ||
      typeof parsed.expiresAt !== "number" ||
      typeof parsed.user !== "object" ||
      parsed.user === null ||
      parsed.expiresAt <= now
    ) {
      clearSession();
      return null;
    }

    if (parsed.user.role !== "supervisor" && parsed.user.role !== "admin") {
      clearSession();
      return null;
    }

    return parsed as DashboardSession;
  } catch {
    clearSession();
    return null;
  }
}
