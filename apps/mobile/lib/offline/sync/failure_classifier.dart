import "../models/sync_state.dart";

enum SyncFailureKind {
  transportUnavailable("transport_unavailable"),
  timeoutOutcomeUnknown("timeout_outcome_unknown"),
  authenticationExpired("authentication_expired"),
  serverRetriable("server_retriable"),
  validationRejected("validation_rejected"),
  authorizationRejected("authorization_rejected"),
  staleEvidence("stale_evidence"),
  lifecycleConflict("lifecycle_conflict"),
  identityConflict("identity_conflict"),
  integrityConflict("integrity_conflict"),
  unknown("unknown");

  const SyncFailureKind(this.code);

  final String code;
}

class SyncFailureDecision {
  const SyncFailureDecision({
    required this.kind,
    required this.targetState,
    required this.autoRetry,
    required this.requiresReconciliation,
  });

  final SyncFailureKind kind;
  final SyncState targetState;
  final bool autoRetry;
  final bool requiresReconciliation;
}

class SyncFailureClassifier {
  const SyncFailureClassifier._();

  static const Set<String> _staleEvidenceCodes = <String>{
    "current_rule_evaluation_required",
    "fresh_rule_evaluation_required",
    "stale_declaration_extraction",
    "stale_ocr_source",
  };

  static const Set<String> _integrityCodes = <String>{
    "capture_integrity_mismatch",
    "capture_storage_integrity_failed",
    "capture_derivative_integrity_mismatch",
    "finalization_snapshot_integrity_failed",
    "finalized_report_integrity_failed",
    "local_evidence_integrity_failed",
    "local_evidence_missing",
    "local_evidence_unavailable",
    "remote_evidence_integrity_mismatch",
  };

  static SyncFailureDecision classify({
    int? statusCode,
    String? apiCode,
    bool transportUnavailable = false,
    bool timedOut = false,
  }) {
    if (transportUnavailable) {
      return const SyncFailureDecision(
        kind: SyncFailureKind.transportUnavailable,
        targetState: SyncState.retryRequired,
        autoRetry: true,
        requiresReconciliation: false,
      );
    }

    if (timedOut) {
      return const SyncFailureDecision(
        kind: SyncFailureKind.timeoutOutcomeUnknown,
        targetState: SyncState.retryRequired,
        autoRetry: false,
        requiresReconciliation: true,
      );
    }

    if (_integrityCodes.contains(apiCode)) {
      return const SyncFailureDecision(
        kind: SyncFailureKind.integrityConflict,
        targetState: SyncState.conflict,
        autoRetry: false,
        requiresReconciliation: true,
      );
    }

    if (_staleEvidenceCodes.contains(apiCode)) {
      return const SyncFailureDecision(
        kind: SyncFailureKind.staleEvidence,
        targetState: SyncState.conflict,
        autoRetry: false,
        requiresReconciliation: true,
      );
    }

    if (apiCode == "client_resource_id_conflict" ||
        apiCode == "remote_identity_mismatch") {
      return const SyncFailureDecision(
        kind: SyncFailureKind.identityConflict,
        targetState: SyncState.conflict,
        autoRetry: false,
        requiresReconciliation: true,
      );
    }

    if (statusCode == 401) {
      return const SyncFailureDecision(
        kind: SyncFailureKind.authenticationExpired,
        targetState: SyncState.blocked,
        autoRetry: false,
        requiresReconciliation: false,
      );
    }

    if (statusCode == 403) {
      return const SyncFailureDecision(
        kind: SyncFailureKind.authorizationRejected,
        targetState: SyncState.blocked,
        autoRetry: false,
        requiresReconciliation: false,
      );
    }

    if (statusCode == 409) {
      return const SyncFailureDecision(
        kind: SyncFailureKind.lifecycleConflict,
        targetState: SyncState.conflict,
        autoRetry: false,
        requiresReconciliation: true,
      );
    }

    if (statusCode == 422) {
      return const SyncFailureDecision(
        kind: SyncFailureKind.validationRejected,
        targetState: SyncState.blocked,
        autoRetry: false,
        requiresReconciliation: false,
      );
    }

    if (statusCode != null && statusCode >= 500) {
      return const SyncFailureDecision(
        kind: SyncFailureKind.serverRetriable,
        targetState: SyncState.retryRequired,
        autoRetry: true,
        requiresReconciliation: false,
      );
    }

    return const SyncFailureDecision(
      kind: SyncFailureKind.unknown,
      targetState: SyncState.blocked,
      autoRetry: false,
      requiresReconciliation: true,
    );
  }
}
