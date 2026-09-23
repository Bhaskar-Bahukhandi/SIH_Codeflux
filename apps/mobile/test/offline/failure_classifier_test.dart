import "package:flutter_test/flutter_test.dart";

import "package:codeflux_mobile/offline/models/sync_state.dart";
import "package:codeflux_mobile/offline/sync/failure_classifier.dart";

void main() {
  test("timeout is outcome-unknown and requires reconciliation", () {
    final decision = SyncFailureClassifier.classify(timedOut: true);

    expect(decision.kind, SyncFailureKind.timeoutOutcomeUnknown);
    expect(decision.targetState, SyncState.retryRequired);
    expect(decision.autoRetry, isFalse);
    expect(decision.requiresReconciliation, isTrue);
  });

  test("transport and generic server failures are retriable", () {
    final transport = SyncFailureClassifier.classify(
      transportUnavailable: true,
    );
    expect(transport.targetState, SyncState.retryRequired);
    expect(transport.autoRetry, isTrue);

    final server = SyncFailureClassifier.classify(statusCode: 503);
    expect(server.kind, SyncFailureKind.serverRetriable);
    expect(server.targetState, SyncState.retryRequired);
    expect(server.autoRetry, isTrue);
  });

  test("authentication and validation failures are blocked", () {
    expect(
      SyncFailureClassifier.classify(statusCode: 401).targetState,
      SyncState.blocked,
    );
    expect(
      SyncFailureClassifier.classify(statusCode: 422).targetState,
      SyncState.blocked,
    );
  });

  test("stale evidence and stable-ID collisions become conflicts", () {
    final stale = SyncFailureClassifier.classify(
      statusCode: 409,
      apiCode: "current_rule_evaluation_required",
    );
    expect(stale.kind, SyncFailureKind.staleEvidence);
    expect(stale.targetState, SyncState.conflict);
    expect(stale.requiresReconciliation, isTrue);

    final identity = SyncFailureClassifier.classify(
      statusCode: 409,
      apiCode: "client_resource_id_conflict",
    );
    expect(identity.kind, SyncFailureKind.identityConflict);
    expect(identity.targetState, SyncState.conflict);

    final remoteIdentity = SyncFailureClassifier.classify(
      statusCode: 409,
      apiCode: "remote_identity_mismatch",
    );
    expect(remoteIdentity.kind, SyncFailureKind.identityConflict);

    final localIntegrity = SyncFailureClassifier.classify(
      statusCode: 409,
      apiCode: "local_evidence_integrity_failed",
    );
    expect(localIntegrity.kind, SyncFailureKind.integrityConflict);

    final remoteIntegrity = SyncFailureClassifier.classify(
      statusCode: 409,
      apiCode: "remote_evidence_integrity_mismatch",
    );
    expect(remoteIntegrity.kind, SyncFailureKind.integrityConflict);
  });
}
