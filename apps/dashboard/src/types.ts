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

export interface Capture {
  id: string;
  inspection_id: string;
  uploader_user_id: string;
  view_type: string;
  original_filename: string | null;
  sha256: string;
  mime_type: string;
  size_bytes: number;
  width_px: number;
  height_px: number;
  created_at: string;
}

export interface CaptureQualityAssessment {
  id: string;
  capture_id: string;
  derivative_id: string;
  algorithm_version: string;
  status: string;
  sharpness_score: number;
  brightness_mean: number;
  dark_fraction: number;
  bright_fraction: number;
  glare_fraction: number;
  reasons: string[];
  thresholds: Record<string, unknown>;
  created_at: string;
}

export interface CaptureGeometryAssessment {
  id: string;
  capture_id: string;
  source_derivative_id: string;
  corrected_derivative_id: string | null;
  algorithm_version: string;
  status: string;
  corners: number[][] | null;
  area_ratio: number | null;
  angle_score: number | null;
  geometry_score: number | null;
  reasons: string[];
  thresholds: Record<string, unknown>;
  created_at: string;
}

export interface OcrBlock {
  id: string;
  run_id: string;
  order_index: number;
  text: string;
  confidence: number;
  polygon: number[][];
}

export interface OcrResult {
  run: {
    id: string;
    capture_id: string;
    source_derivative_id: string;
    source_sha256: string;
    engine_name: string;
    engine_version: string;
    model_version: string;
    language: string;
    parameters: Record<string, unknown>;
    block_count: number;
    created_at: string;
  };
  blocks: OcrBlock[];
}

export interface DeclarationExtractionResult {
  run: {
    id: string;
    inspection_id: string;
    actor_user_id: string;
    extractor_version: string;
    fusion_version: string;
    inspection_capture_count: number;
    source_capture_count: number;
    source_capture_ids: string[];
    source_ocr_run_ids: string[];
    skipped_sources: Array<Record<string, unknown>>;
    observation_count: number;
    created_at: string;
  };
  observations: Array<{
    id: string;
    extraction_run_id: string;
    declaration_type: string;
    capture_id: string;
    ocr_run_id: string;
    raw_text: string;
    normalized_value: Record<string, unknown>;
    ocr_confidence_min: number;
    ocr_confidence_mean: number;
    extractor_method: string;
    source_block_ids: string[];
  }>;
  summaries: Array<{
    id: string;
    extraction_run_id: string;
    declaration_type: string;
    status: string;
    canonical_value: Record<string, unknown> | null;
    candidate_values: Array<Record<string, unknown>>;
    observation_count: number;
    capture_count: number;
  }>;
}

export interface RuleEvaluationResponse {
  run: {
    id: string;
    inspection_id: string;
    actor_user_id: string;
    source_extraction_run_id: string;
    rule_pack_id: string;
    rule_pack_version: string;
    rule_pack_sha256: string;
    rule_pack_snapshot: Record<string, unknown>;
    context_snapshot: Record<string, unknown>;
    result_count: number;
    created_at: string;
  };
  results: Array<{
    id: string;
    evaluation_run_id: string;
    rule_id: string;
    provision: string;
    declaration_type: string;
    status: string;
    evidence_summary_id: string | null;
    explanation: string;
    details: Record<string, unknown>;
  }>;
}

export interface OfficerRuleReview {
  id: string;
  inspection_id: string;
  officer_user_id: string;
  rule_evaluation_run_id: string;
  rule_evaluation_result_id: string;
  revision: number;
  decision: string;
  corrected_value: Record<string, unknown> | null;
  note: string | null;
  created_at: string;
}

export interface OfficerReviewHistory {
  reviews: OfficerRuleReview[];
  latest_by_rule_result: Record<string, OfficerRuleReview>;
}

export interface InspectionFinalization {
  id: string;
  inspection_id: string;
  finalized_by_user_id: string;
  rule_evaluation_run_id: string;
  rule_pack_id: string;
  rule_pack_version: string;
  rule_pack_sha256: string;
  snapshot: Record<string, unknown>;
  snapshot_sha256: string;
  report_id: string;
  report_version: string;
  report_sha256: string;
  report_size_bytes: number;
  finalized_at: string;
}

export interface CaptureEvidenceState {
  capture: Capture;
  quality: CaptureQualityAssessment | null;
  geometry: CaptureGeometryAssessment | null;
  ocr: OcrResult | null;
}

export interface InspectionDetailState {
  inspection: Inspection;
  captures: CaptureEvidenceState[];
  declarations: DeclarationExtractionResult | null;
  ruleEvaluation: RuleEvaluationResponse | null;
  reviews: OfficerReviewHistory;
  finalization: InspectionFinalization | null;
}

export interface ApiErrorPayload {
  error?: {
    code?: string;
    message?: string;
  };
  detail?: string;
}
