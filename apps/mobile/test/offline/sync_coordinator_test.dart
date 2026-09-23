import "dart:io";

import "package:flutter_test/flutter_test.dart";
import "package:path/path.dart" as p;
import "package:sqflite_common_ffi/sqflite_ffi.dart";

import "package:codeflux_mobile/offline/models/sync_operation.dart";
import "package:codeflux_mobile/offline/models/sync_state.dart";
import "package:codeflux_mobile/offline/persistence/local_draft_repository.dart";
import "package:codeflux_mobile/offline/persistence/offline_database.dart";
import "package:codeflux_mobile/offline/persistence/sync_queue_repository.dart";
import "package:codeflux_mobile/offline/sync/sync_coordinator.dart";

const inspectionId = "55555555-5555-4555-8555-555555555555";
const operationId = "66666666-6666-4666-8666-666666666666";

class FakeExecutor implements SyncOperationExecutor {
  FakeExecutor(this.handler);

  final Future<SyncExecutionSuccess> Function(SyncOperation) handler;
  int calls = 0;

  @override
  Future<SyncExecutionSuccess> execute(SyncOperation operation) {
    calls += 1;
    return handler(operation);
  }
}

class FakeReconciler implements SyncOperationReconciler {
  FakeReconciler(this.result);

  final ReconciliationResult result;
  int calls = 0;

  @override
  Future<ReconciliationResult> reconcile(SyncOperation operation) async {
    calls += 1;
    return result;
  }
}

void main() {
  late Directory tempDirectory;
  late OfflineDatabase offlineDatabase;
  late SyncQueueRepository queue;

  setUpAll(() {
    sqfliteFfiInit();
  });

  setUp(() async {
    tempDirectory = await Directory.systemTemp.createTemp(
      "codeflux_coordinator_test_",
    );
    offlineDatabase = await OfflineDatabase.openAt(
      p.join(tempDirectory.path, "offline.sqlite3"),
      factory: databaseFactoryFfi,
    );
    final drafts = LocalDraftRepository(offlineDatabase);
    await drafts.createInspection(
      id: inspectionId,
      productName: "Coordinator Product",
    );
    queue = SyncQueueRepository(offlineDatabase);
  });

  tearDown(() async {
    await offlineDatabase.close();
    if (await tempDirectory.exists()) {
      await tempDirectory.delete(recursive: true);
    }
  });

  Future<void> enqueueOperation(DateTime now) async {
    await queue.enqueue(
      SyncOperation.queued(
        id: operationId,
        inspectionId: inspectionId,
        type: SyncOperationType.createInspection,
        resourceId: inspectionId,
        payload: const <String, Object?>{
          "id": inspectionId,
          "product_name": "Coordinator Product",
        },
        now: now,
      ),
    );
  }

  test("successful execution marks operation synced", () async {
    final now = DateTime.utc(2026, 9, 23, 17);
    await enqueueOperation(now);
    final executor = FakeExecutor(
      (_) async => const SyncExecutionSuccess(
        remoteResourceId: inspectionId,
      ),
    );
    final coordinator = SyncCoordinator(
      queue: queue,
      executor: executor,
    );

    final result = await coordinator.runNext(now: now);

    expect(result.status, SyncCycleStatus.synced);
    expect(executor.calls, 1);
    final stored = await queue.getById(operationId);
    expect(stored!.state, SyncState.synced);
    expect(stored.remoteResourceId, inspectionId);
  });

  test("timeout reconciled as applied does not replay mutation", () async {
    final now = DateTime.utc(2026, 9, 23, 18);
    await enqueueOperation(now);
    final executor = FakeExecutor(
      (_) async => throw const SyncRequestFailure(
        timedOut: true,
        message: "Response was lost.",
      ),
    );
    final reconciler = FakeReconciler(
      const ReconciliationResult.applied(
        remoteResourceId: inspectionId,
      ),
    );
    final coordinator = SyncCoordinator(
      queue: queue,
      executor: executor,
      reconciler: reconciler,
    );

    final result = await coordinator.runNext(now: now);

    expect(result.status, SyncCycleStatus.synced);
    expect(executor.calls, 1);
    expect(reconciler.calls, 1);
    expect((await queue.getById(operationId))!.state, SyncState.synced);
  });

  test("unresolved timeout parks operation for reconciliation", () async {
    final now = DateTime.utc(2026, 9, 23, 19);
    await enqueueOperation(now);
    final executor = FakeExecutor(
      (_) async => throw const SyncRequestFailure(timedOut: true),
    );
    final coordinator = SyncCoordinator(
      queue: queue,
      executor: executor,
      reconciler: FakeReconciler(
        const ReconciliationResult.unresolved(),
      ),
    );

    final result = await coordinator.runNext(now: now);

    expect(result.status, SyncCycleStatus.reconciliationRequired);
    final stored = await queue.getById(operationId);
    expect(stored!.state, SyncState.retryRequired);
    expect(stored.nextAttemptAt, isNull);

    final blindReplay = await coordinator.runNext(
      now: now.add(const Duration(hours: 1)),
    );
    expect(blindReplay.status, SyncCycleStatus.idle);
    expect(executor.calls, 1);
  });

  test("parked timeout can be reconciled later after recovery", () async {
    final now = DateTime.utc(2026, 9, 23, 19, 30);
    await enqueueOperation(now);
    final executor = FakeExecutor(
      (_) async => throw const SyncRequestFailure(timedOut: true),
    );
    final initialCoordinator = SyncCoordinator(
      queue: queue,
      executor: executor,
      reconciler: FakeReconciler(
        const ReconciliationResult.unresolved(),
      ),
    );

    final initial = await initialCoordinator.runNext(now: now);
    expect(initial.status, SyncCycleStatus.reconciliationRequired);

    final recoveredCoordinator = SyncCoordinator(
      queue: queue,
      executor: executor,
      reconciler: FakeReconciler(
        const ReconciliationResult.applied(
          remoteResourceId: inspectionId,
        ),
      ),
    );
    final reconciled = await recoveredCoordinator.reconcilePending(
      operationId,
      now: now.add(const Duration(minutes: 5)),
    );

    expect(reconciled.status, SyncCycleStatus.synced);
    expect((await queue.getById(operationId))!.state, SyncState.synced);
    expect(executor.calls, 1);
  });

  test("verified not-applied timeout schedules safe retry", () async {
    final now = DateTime.utc(2026, 9, 23, 20);
    await enqueueOperation(now);
    final executor = FakeExecutor(
      (_) async => throw const SyncRequestFailure(timedOut: true),
    );
    final coordinator = SyncCoordinator(
      queue: queue,
      executor: executor,
      reconciler: FakeReconciler(
        const ReconciliationResult.notApplied(),
      ),
    );

    final result = await coordinator.runNext(now: now);

    expect(result.status, SyncCycleStatus.retryScheduled);
    final stored = await queue.getById(operationId);
    expect(stored!.state, SyncState.retryRequired);
    expect(stored.nextAttemptAt, isNotNull);
  });

  test("unverifiable success response is reconciled before replay", () async {
    final now = DateTime.utc(2026, 9, 23, 20, 15);
    await enqueueOperation(now);
    final executor = FakeExecutor(
      (_) async => throw const SyncRequestFailure(
        apiCode: "response_unverifiable",
        message: "Success body could not be verified.",
        outcomeUnknown: true,
      ),
    );
    final reconciler = FakeReconciler(
      const ReconciliationResult.applied(
        remoteResourceId: inspectionId,
      ),
    );
    final coordinator = SyncCoordinator(
      queue: queue,
      executor: executor,
      reconciler: reconciler,
    );

    final result = await coordinator.runNext(now: now);

    expect(result.status, SyncCycleStatus.synced);
    expect(executor.calls, 1);
    expect(reconciler.calls, 1);
    expect((await queue.getById(operationId))!.state, SyncState.synced);
  });

  test("transport failure is reconciled before retry", () async {
    final now = DateTime.utc(2026, 9, 23, 20, 30);
    await enqueueOperation(now);
    final executor = FakeExecutor(
      (_) async => throw const SyncRequestFailure(
        transportUnavailable: true,
        message: "Connection dropped.",
      ),
    );
    final coordinator = SyncCoordinator(
      queue: queue,
      executor: executor,
      reconciler: FakeReconciler(
        const ReconciliationResult.notApplied(),
      ),
    );

    final result = await coordinator.runNext(now: now);

    expect(result.status, SyncCycleStatus.retryScheduled);
    expect(executor.calls, 1);
    final stored = await queue.getById(operationId);
    expect(stored!.state, SyncState.retryRequired);
    expect(stored.nextAttemptAt, isNotNull);
  });

  test("5xx response reconciled as applied is not replayed", () async {
    final now = DateTime.utc(2026, 9, 23, 20, 45);
    await enqueueOperation(now);
    final executor = FakeExecutor(
      (_) async => throw const SyncRequestFailure(
        statusCode: 503,
        apiCode: "service_unavailable",
      ),
    );
    final reconciler = FakeReconciler(
      const ReconciliationResult.applied(
        remoteResourceId: inspectionId,
      ),
    );
    final coordinator = SyncCoordinator(
      queue: queue,
      executor: executor,
      reconciler: reconciler,
    );

    final result = await coordinator.runNext(now: now);

    expect(result.status, SyncCycleStatus.synced);
    expect(executor.calls, 1);
    expect(reconciler.calls, 1);
    expect((await queue.getById(operationId))!.state, SyncState.synced);
  });

  test("authentication expiry blocks until credentials are resolved", () async {
    final now = DateTime.utc(2026, 9, 23, 20, 50);
    await enqueueOperation(now);
    final coordinator = SyncCoordinator(
      queue: queue,
      executor: FakeExecutor(
        (_) async => throw const SyncRequestFailure(
          statusCode: 401,
          apiCode: "invalid_or_expired_token",
          message: "Authentication expired.",
        ),
      ),
    );

    final result = await coordinator.runNext(now: now);

    expect(result.status, SyncCycleStatus.blocked);
    final stored = await queue.getById(operationId);
    expect(stored!.state, SyncState.blocked);
    expect(stored.nextAttemptAt, isNull);
  });

  test("stale evidence rejection becomes explicit conflict", () async {
    final now = DateTime.utc(2026, 9, 23, 20, 55);
    await enqueueOperation(now);
    final coordinator = SyncCoordinator(
      queue: queue,
      executor: FakeExecutor(
        (_) async => throw const SyncRequestFailure(
          statusCode: 409,
          apiCode: "current_rule_evaluation_required",
          message: "Evidence is stale.",
        ),
      ),
    );

    final result = await coordinator.runNext(now: now);

    expect(result.status, SyncCycleStatus.conflict);
    final stored = await queue.getById(operationId);
    expect(stored!.state, SyncState.conflict);
    expect(stored.nextAttemptAt, isNull);
  });

  test("semantic validation rejection becomes blocked", () async {
    final now = DateTime.utc(2026, 9, 23, 21);
    await enqueueOperation(now);
    final coordinator = SyncCoordinator(
      queue: queue,
      executor: FakeExecutor(
        (_) async => throw const SyncRequestFailure(
          statusCode: 422,
          apiCode: "invalid_image",
          message: "Image is invalid.",
        ),
      ),
    );

    final result = await coordinator.runNext(now: now);

    expect(result.status, SyncCycleStatus.blocked);
    expect((await queue.getById(operationId))!.state, SyncState.blocked);
  });
}
