import type {
  AccessTokenResponse,
  ApiErrorPayload,
  Capture,
  CaptureGeometryAssessment,
  CaptureQualityAssessment,
  CurrentUser,
  DeclarationExtractionResult,
  Inspection,
  InspectionFinalization,
  OcrResult,
  OfficerReviewHistory,
  RuleEvaluationResponse,
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
    // Structured API errors are expected, but proxy failures may not be JSON.
  }

  const message =
    payload?.error?.message ??
    payload?.detail ??
    `Request failed with status ${response.status}.`;
  return new ApiError(message, response.status, payload?.error?.code ?? null);
}

async function request(
  path: string,
  init: RequestInit = {},
  accessToken?: string,
): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  try {
    return await fetch(`${API_PREFIX}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      "The CODEFLUX API could not be reached. Check the API service and dashboard proxy configuration.",
      0,
      "network_error",
    );
  }
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  accessToken?: string,
): Promise<T> {
  const response = await request(path, init, accessToken);
  if (!response.ok) throw await readError(response);
  return (await response.json()) as T;
}

async function requestOptionalJson<T>(
  path: string,
  accessToken: string,
): Promise<T | null> {
  const response = await request(path, {}, accessToken);
  if (response.status === 404) return null;
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

export function getInspection(
  inspectionId: string,
  accessToken: string,
): Promise<Inspection> {
  return requestJson<Inspection>(
    `/inspections/${encodeURIComponent(inspectionId)}`,
    {},
    accessToken,
  );
}

export function listCaptures(
  inspectionId: string,
  accessToken: string,
): Promise<Capture[]> {
  return requestJson<Capture[]>(
    `/inspections/${encodeURIComponent(inspectionId)}/captures`,
    {},
    accessToken,
  );
}

export function getLatestQuality(
  inspectionId: string,
  captureId: string,
  accessToken: string,
): Promise<CaptureQualityAssessment | null> {
  return requestOptionalJson<CaptureQualityAssessment>(
    `/inspections/${encodeURIComponent(inspectionId)}/captures/${encodeURIComponent(captureId)}/quality/latest`,
    accessToken,
  );
}

export function getLatestGeometry(
  inspectionId: string,
  captureId: string,
  accessToken: string,
): Promise<CaptureGeometryAssessment | null> {
  return requestOptionalJson<CaptureGeometryAssessment>(
    `/inspections/${encodeURIComponent(inspectionId)}/captures/${encodeURIComponent(captureId)}/geometry/latest`,
    accessToken,
  );
}

export function getLatestOcr(
  inspectionId: string,
  captureId: string,
  accessToken: string,
): Promise<OcrResult | null> {
  return requestOptionalJson<OcrResult>(
    `/inspections/${encodeURIComponent(inspectionId)}/captures/${encodeURIComponent(captureId)}/ocr/latest`,
    accessToken,
  );
}

export function getLatestDeclarations(
  inspectionId: string,
  accessToken: string,
): Promise<DeclarationExtractionResult | null> {
  return requestOptionalJson<DeclarationExtractionResult>(
    `/inspections/${encodeURIComponent(inspectionId)}/declarations/latest`,
    accessToken,
  );
}

export function getLatestRuleEvaluation(
  inspectionId: string,
  accessToken: string,
): Promise<RuleEvaluationResponse | null> {
  return requestOptionalJson<RuleEvaluationResponse>(
    `/inspections/${encodeURIComponent(inspectionId)}/rule-evaluations/latest`,
    accessToken,
  );
}

export function getRuleReviews(
  inspectionId: string,
  accessToken: string,
): Promise<OfficerReviewHistory> {
  return requestJson<OfficerReviewHistory>(
    `/inspections/${encodeURIComponent(inspectionId)}/rule-reviews`,
    {},
    accessToken,
  );
}

export function getFinalization(
  inspectionId: string,
  accessToken: string,
): Promise<InspectionFinalization | null> {
  return requestOptionalJson<InspectionFinalization>(
    `/inspections/${encodeURIComponent(inspectionId)}/finalization`,
    accessToken,
  );
}

export async function getFinalizedReport(
  inspectionId: string,
  accessToken: string,
): Promise<{ blob: Blob; filename: string }> {
  const response = await request(
    `/inspections/${encodeURIComponent(inspectionId)}/finalization/report`,
    { headers: { Accept: "application/pdf" } },
    accessToken,
  );
  if (!response.ok) throw await readError(response);

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filenameMatch = disposition.match(/filename="([^"]+)"/i);
  return {
    blob: await response.blob(),
    filename: filenameMatch?.[1] ?? `CODEFLUX-${inspectionId}.pdf`,
  };
}
