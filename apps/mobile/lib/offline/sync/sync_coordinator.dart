import "../models/sync_operation.dart";
import "../models/sync_state.dart";
import "../persistence/sync_queue_repository.dart";
import "failure_classifier.dart";
import "retry_policy.dart";

class SyncExecutionSuccess {
  const SyncExecutionSuccess({this.remoteResourceId});

  final String? remoteResourceId;
}

class SyncRequestFailure implements Exception {
  const SyncRequestFailure({
    this.statusCode,
    this.apiCode,
    this.message,
    this.transportUnavailable = false,
    this.timedOut = false,
  });

  final int? statusCode;
  final String? apiCode;
  final String? message;
  final bool transportUnavailable;
  final bool timedOut;
}

abstract interface class SyncOperationExecutor {
  Future<SyncExecutionSuccess> execute(SyncOperation operation);
}

enum ReconciliationStatus {
  applied,
  notApplied,
  unresolved,
}

class ReconciliationResult {
  const ReconciliationResult._(
    this.status, {
    this.remoteResourceId,
  });

  const ReconciliationResult.applied({String? remoteResourceId})
      : this._(
          ReconciliationStatus.applied,
          remoteResourceId: remoteResourceId,
        );

  const ReconciliationResult.notApplied()
      : this._(ReconciliationStatus.notApplied);

  const ReconciliationResult.unresolved()
      : this._(ReconciliationStatus.unresolved);

  final ReconciliationStatus status;
  final String? remoteResourceId;
}

abstract interface class SyncOperationReconciler {
  Future<ReconciliationResult> reconcile(SyncOperation operation);
}

enum SyncCycleStatus {
  idle,
  synced,
  retryScheduled,
  blocked,
  conflict,
  reconciliationRequired,
}

class SyncCycleResult {
  const SyncCycleResult({
    required this.status,
    this.operationId,
  });

  final SyncCycleStatus status;
  final String? operationId;
}

class SyncCoordinator {
  const SyncCoordinator({
    required this.queue,
    required this.executor,
    this.reconciler,
    this.retryPolicy = const SyncRetryPolicy(),
  });

  final SyncQueueRepository queue;
  final SyncOperationExecutor executor;
  final SyncOperationReconciler? reconciler;
  final SyncRetryPolicy retryPolicy;

  Future<SyncCycleResult> runNext({DateTime? now}) async {
    final timestamp = (now ?? DateTime.now().toUtc()).toUtc();
    final operation = await queue.claimNextReady(timestamp);
    if (operation == null) {
      return const SyncCycleResult(status: SyncCycleStatus.idle);
    }

    try {
      final result = await executor.execute(operation);
      await queue.markSynced(
        operation.id,
        remoteResourceId: result.remoteResourceId,
        now: timestamp,
      );
      return SyncCycleResult(
        status: SyncCycleStatus.synced,
        operationId: operation.id,
      );
    } on SyncRequestFailure catch (failure) {
      final decision = SyncFailureClassifier.classify(
        statusCode: failure.statusCode,
        apiCode: failure.apiCode,
        transportUnavailable: failure.transportUnavailable,
        timedOut: failure.timedOut,
      );

      if (decision.targetState == SyncState.retryRequired &&
          decision.requiresReconciliation) {
        ReconciliationResult reconciliation;
        try {
          reconciliation = reconciler == null
              ? const ReconciliationResult.unresolved()
              : await reconciler!.reconcile(operation);
        } on SyncRequestFailure catch (reconciliationFailure) {
          await queue.markFailure(
            operation.id,
            decision: decision,
            retryPolicy: retryPolicy,
            apiCode: reconciliationFailure.apiCode,
            message: reconciliationFailure.message,
            now: timestamp,
          );
          return SyncCycleResult(
            status: SyncCycleStatus.reconciliationRequired,
            operationId: operation.id,
          );
        }

        if (reconciliation.status == ReconciliationStatus.applied) {
          await queue.markSynced(
            operation.id,
            remoteResourceId: reconciliation.remoteResourceId,
            now: timestamp,
          );
          return SyncCycleResult(
            status: SyncCycleStatus.synced,
            operationId: operation.id,
          );
        }

        if (reconciliation.status == ReconciliationStatus.notApplied) {
          await queue.markFailure(
            operation.id,
            decision: SyncFailureDecision(
              kind: decision.kind,
              targetState: SyncState.retryRequired,
              autoRetry: true,
              requiresReconciliation: false,
            ),
            retryPolicy: retryPolicy,
            apiCode: failure.apiCode,
            message: failure.message,
            now: timestamp,
          );
          return SyncCycleResult(
            status: SyncCycleStatus.retryScheduled,
            operationId: operation.id,
          );
        }
      }

      await queue.markFailure(
        operation.id,
        decision: decision,
        retryPolicy: retryPolicy,
        apiCode: failure.apiCode,
        message: failure.message,
        now: timestamp,
      );

      final updated = await queue.getById(operation.id);
      final status = switch (updated!.state) {
        SyncState.retryRequired => decision.requiresReconciliation
            ? SyncCycleStatus.reconciliationRequired
            : SyncCycleStatus.retryScheduled,
        SyncState.conflict => SyncCycleStatus.conflict,
        SyncState.blocked => SyncCycleStatus.blocked,
        _ => throw StateError(
            "Failure handling produced an invalid queue state.",
          ),
      };

      return SyncCycleResult(
        status: status,
        operationId: operation.id,
      );
    }
  }

  Future<SyncCycleResult> reconcilePending(
    String operationId, {
    DateTime? now,
  }) async {
    final timestamp = (now ?? DateTime.now().toUtc()).toUtc();
    final operation = await queue.getById(operationId);
    if (operation == null) {
      throw StateError("Sync operation does not exist.");
    }
    if (operation.state != SyncState.retryRequired ||
        operation.nextAttemptAt != null) {
      throw StateError(
        "Operation is not parked waiting for reconciliation.",
      );
    }
    if (reconciler == null) {
      return SyncCycleResult(
        status: SyncCycleStatus.reconciliationRequired,
        operationId: operation.id,
      );
    }

    ReconciliationResult reconciliation;
    try {
      reconciliation = await reconciler!.reconcile(operation);
    } on SyncRequestFailure catch (failure) {
      await queue.recordReconciliationFailure(
        operation.id,
        apiCode: failure.apiCode,
        message: failure.message,
        now: timestamp,
      );
      return SyncCycleResult(
        status: SyncCycleStatus.reconciliationRequired,
        operationId: operation.id,
      );
    }

    switch (reconciliation.status) {
      case ReconciliationStatus.applied:
        await queue.markSynced(
          operation.id,
          remoteResourceId: reconciliation.remoteResourceId,
          reconciledAfterUnknownOutcome: true,
          now: timestamp,
        );
        return SyncCycleResult(
          status: SyncCycleStatus.synced,
          operationId: operation.id,
        );
      case ReconciliationStatus.notApplied:
        await queue.scheduleRetryAfterReconciliation(
          operation.id,
          retryPolicy: retryPolicy,
          now: timestamp,
        );
        final updated = await queue.getById(operation.id);
        return SyncCycleResult(
          status: updated!.state == SyncState.blocked
              ? SyncCycleStatus.blocked
              : SyncCycleStatus.retryScheduled,
          operationId: operation.id,
        );
      case ReconciliationStatus.unresolved:
        return SyncCycleResult(
          status: SyncCycleStatus.reconciliationRequired,
          operationId: operation.id,
        );
    }
  }
}
