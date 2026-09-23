import "package:http/http.dart" as http;

import "../../auth/officer_session_store.dart";
import "../models/sync_operation.dart";
import "../persistence/local_draft_repository.dart";
import "codeflux_api_sync_adapter.dart";
import "sync_coordinator.dart";

class SessionBoundSyncAdapter
    implements SyncOperationExecutor, SyncOperationReconciler {
  SessionBoundSyncAdapter({
    required http.Client client,
    required Uri serverBaseUri,
    required OfficerSessionStore sessionStore,
    required LocalDraftRepository drafts,
    Duration requestTimeout = const Duration(seconds: 20),
    DateTime Function()? now,
  })  : _sessionStore = sessionStore,
        _drafts = drafts,
        _now = now ?? (() => DateTime.now().toUtc()),
        _inner = CodefluxApiSyncAdapter(
          client: client,
          serverBaseUri: serverBaseUri,
          accessTokenProvider: OfficerSessionTokenProvider(
            sessionStore,
            now: now,
          ).call,
          requestTimeout: requestTimeout,
        );

  final OfficerSessionStore _sessionStore;
  final LocalDraftRepository _drafts;
  final DateTime Function() _now;
  final CodefluxApiSyncAdapter _inner;

  @override
  Future<SyncExecutionSuccess> execute(SyncOperation operation) async {
    await _requireOwnership(operation);
    return _inner.execute(operation);
  }

  @override
  Future<ReconciliationResult> reconcile(SyncOperation operation) async {
    await _requireOwnership(operation);
    return _inner.reconcile(operation);
  }

  Future<void> _requireOwnership(SyncOperation operation) async {
    final draft = await _drafts.getInspection(operation.inspectionId);
    if (draft == null) {
      throw const SyncRequestFailure(
        statusCode: 409,
        apiCode: "local_inspection_missing",
        message:
            "The queued inspection is missing from local persistent storage.",
      );
    }

    OfficerSessionContext? session;
    try {
      session = await _sessionStore.read();
    } on FormatException {
      throw const SyncRequestFailure(
        statusCode: 401,
        apiCode: "local_session_invalid",
        message:
            "The locally stored Officer session is invalid and must be renewed.",
      );
    }

    if (session == null) {
      throw const SyncRequestFailure(
        statusCode: 401,
        apiCode: "local_session_missing",
        message: "Officer authentication is required before synchronization.",
      );
    }

    if (session.tokenExpired(now: _now())) {
      throw const SyncRequestFailure(
        statusCode: 401,
        apiCode: "local_session_expired",
        message:
            "The Officer session expired. Re-authentication is required before synchronization.",
      );
    }

    if (session.role != "officer") {
      throw const SyncRequestFailure(
        statusCode: 403,
        apiCode: "local_officer_role_required",
        message:
            "Only an authenticated Officer session may synchronize field inspections.",
      );
    }

    if (draft.officerUserId == null) {
      throw const SyncRequestFailure(
        statusCode: 403,
        apiCode: "local_inspection_owner_unverified",
        message:
            "This legacy local inspection has no verified Officer owner and cannot be synchronized automatically.",
      );
    }

    if (draft.officerUserId != session.userId) {
      throw const SyncRequestFailure(
        statusCode: 403,
        apiCode: "local_officer_mismatch",
        message:
            "The active Officer does not own this local inspection. Switch back to the owning Officer before synchronization.",
      );
    }
  }
}
