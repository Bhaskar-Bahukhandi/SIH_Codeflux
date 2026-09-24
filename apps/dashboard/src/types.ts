export type UserRole = "officer" | "supervisor" | "admin";
export type InspectionStatus = "draft" | "pending_review" | "finalized";

export interface CurrentUser {
  id: string;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export interface AccessTokenResponse {
  access_token: string;
  token_type: "bearer" | string;
  expires_in: number;
}

export interface Inspection {
  id: string;
  product_name: string;
  product_identifier: string | null;
  officer_id: string | null;
  status: InspectionStatus;
  submitted_at: string | null;
  reopened_for_recheck_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApiErrorPayload {
  error?: {
    code?: string;
    message?: string;
  };
  detail?: string;
}
