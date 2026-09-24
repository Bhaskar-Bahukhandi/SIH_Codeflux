import type {
  AccessTokenResponse,
  ApiErrorPayload,
  CurrentUser,
  Inspection,
} from "./types";

const API_PREFIX = "/api/v1";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function readError(response: Response): Promise<ApiError> {
  let payload: ApiErrorPayload | null = null;
  try {
    payload = (await response.json()) as ApiErrorPayload;
  } catch {
    // The API normally returns structured errors, but a proxy/network edge may not.
  }

  const message =
    payload?.error?.message ??
    payload?.detail ??
    `Request failed with status ${response.status}.`;
  return new ApiError(message, response.status, payload?.error?.code ?? null);
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  accessToken?: string,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      "The CODEFLUX API could not be reached. Check the API service and dashboard proxy configuration.",
      0,
      "network_error",
    );
  }

  if (!response.ok) throw await readError(response);
  return (await response.json()) as T;
}

export function login(email: string, password: string): Promise<AccessTokenResponse> {
  return requestJson<AccessTokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function getCurrentUser(accessToken: string): Promise<CurrentUser> {
  return requestJson<CurrentUser>("/auth/me", {}, accessToken);
}

export function listInspections(accessToken: string): Promise<Inspection[]> {
  return requestJson<Inspection[]>("/inspections", {}, accessToken);
}
