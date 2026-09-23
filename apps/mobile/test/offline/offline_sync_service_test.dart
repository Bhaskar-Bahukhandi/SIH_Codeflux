import "dart:io";

import "package:flutter_test/flutter_test.dart";
import "package:path/path.dart" as p;
import "package:sqflite_common_ffi/sqflite_ffi.dart";

import "package:codeflux_mobile/offline/models/sync_operation.dart";
import "package:codeflux_mobile/offline/models/sync_state.dart";
import "package:codeflux_mobile/offline/persistence/local_draft_repository.dart";
import "package:codeflux_mobile/offline/persistence/offline_database.dart";
import "package:codeflux_mobile/offline/persistence/sync_queue_repository.dart";
import "package:codeflux_mobile/offline/sync/offline_sync_service.dart";
import "package:codeflux_mobile/offline/sync/sync_coordinator.dart";

class SequenceExecutor implements SyncOperationExecutor {
  SequenceExecutor(this.failIds);

  final Set<String> failIds;
  final List<String> executedIds = <String>[];

  @override
  Future<SyncExecutionSuccess> execute(SyncOperation operation) async {
    executedIds.add(operation.id);
    if (failIds.contains(operation.id)) {
      throw const SyncRequestFailure(
        statusCode: 422,
        apiCode: "validation_failed",
        message: "Synthetic validation rejection.",
      );
    }
    return SyncExecutionSuccess(
      remoteResourceId: operation.resourceId,
    );
  }
}

class AppliedReconciler implements SyncOperationReconciler {
  final List<String> reconciledIds = <String>[];

  @override
  Future<ReconciliationResult> reconcile(SyncOperation operation) async {
    reconciledIds.add(operation.id);
    return ReconciliationResult.applied(
      remoteResourceId: operation.resourceId,
    );
  }
}

void main() {
  setUpAll(() {
    sqfliteFfiInit();
  });

  test("drain continues past blocked work and syncs independent inspection", () async {
    final root = await Directory.systemTemp.createTemp(
      "codeflux_sync_service_",
    );
    late OfflineDatabase database;
    addTearDown(() async {
      try {
        await database.close();
      } catch (_) {}
      if (await root.exists()) {
        await root.delete(recursive: true);
      }
    });

    database = await OfflineDatabase.openAt(
      p.join(root.path, "offline.sqlite3"),
      factory: databaseFactoryFfi,
    );
    final drafts = LocalDraftRepository(database);
    final queue = SyncQueueRepository(database);

    const firstInspection = "17171717-1717-4717-8717-171717171717";
    const secondInspection = "18181818-1818-4818-8818-181818181818";
    const firstOperation = "19191919-1919-4919-8919-191919191919";
    const secondOperation = "20202020-2020-4020-8020-202020202020";

    await drafts.createInspection(
      id: firstInspection,
      officerUserId: "officer-1",
      productName: "Invalid Local Draft",
    );
    await drafts.createInspection(
      id: secondInspection,
      officerUserId: "officer-1",
      productName: "Independent Draft",
    );

    await queue.enqueue(
      SyncOperation.queued(
        id: firstOperation,
        inspectionId: firstInspection,
        type: SyncOperationType.createInspection,
        resourceId: firstInspection,
        payload: const <String, Object?>{
          "id": firstInspection,
          "product_name": "Invalid Local Draft",
        },
      ),
    );
    await queue.enqueue(
      SyncOperation.queued(
        id: secondOperation,
        inspectionId: secondInspection,
        type: SyncOperationType.createInspection,
        resourceId: secondInspection,
        payload: const <String, Object?>{
          "id": secondInspection,
          "product_name": "Independent Draft",
        },
      ),
    );

    final executor = SequenceExecutor(<String>{firstOperation});
    final service = OfflineSyncService(
      coordinator: SyncCoordinator(
        queue: queue,
        executor: executor,
      ),
    );

    final summary = await service.drain(
      now: DateTime.utc(2026, 9, 24, 0),
    );

    expect(summary.processed, 2);
    expect(summary.blocked, 1);
    expect(summary.synced, 1);
    expect(summary.limitReached, isFalse);
    expect(
      (await queue.getById(firstOperation))!.state,
      SyncState.blocked,
    );
    expect(
      (await queue.getById(secondOperation))!.state,
      SyncState.synced,
    );
    expect(
      (await drafts.getInspection(firstInspection))!.syncState,
      SyncState.blocked,
    );
    expect(
      (await drafts.getInspection(secondInspection))!.syncState,
      SyncState.synced,
    );
  });

  test("startup recovery reconciles interrupted work before replay", () async {
    final root = await Directory.systemTemp.createTemp(
      "codeflux_sync_recovery_",
    );
    late OfflineDatabase database;
    addTearDown(() async {
      try {
        await database.close();
      } catch (_) {}
      if (await root.exists()) {
        await root.delete(recursive: true);
      }
    });

    database = await OfflineDatabase.openAt(
      p.join(root.path, "offline.sqlite3"),
      factory: databaseFactoryFfi,
    );
    final drafts = LocalDraftRepository(database);
    final queue = SyncQueueRepository(database);

    const inspectionId = "21212121-2121-4121-8121-212121212121";
    const operationId = "22222222-aaaa-4222-8222-222222222222";
    final now = DateTime.utc(2026, 9, 24, 1);

    await drafts.createInspection(
      id: inspectionId,
      officerUserId: "officer-1",
      productName: "Interrupted Draft",
    );
    await queue.enqueue(
      SyncOperation.queued(
        id: operationId,
        inspectionId: inspectionId,
        type: SyncOperationType.createInspection,
        resourceId: inspectionId,
        payload: const <String, Object?>{
          "id": inspectionId,
          "product_name": "Interrupted Draft",
        },
      ),
    );
    final claimed = await queue.claimNextReady(now);
    expect(claimed!.state, SyncState.syncing);

    final executor = SequenceExecutor(<String>{});
    final reconciler = AppliedReconciler();
    final service = OfflineSyncService(
      coordinator: SyncCoordinator(
        queue: queue,
        executor: executor,
        reconciler: reconciler,
      ),
    );
    final summary = await service.recoverAndDrain(
      now: now.add(const Duration(minutes: 1)),
    );

    expect(summary.recoveredInterrupted, 1);
    expect(summary.processed, 1);
    expect(summary.synced, 1);
    expect(reconciler.reconciledIds, <String>[operationId]);
    expect(executor.executedIds, isEmpty);
    expect(
      (await queue.getById(operationId))!.state,
      SyncState.synced,
    );
    expect(
      (await drafts.getInspection(inspectionId))!.syncState,
      SyncState.synced,
    );
  });

  test("drain obeys a hard per-cycle operation limit", () async {
    final root = await Directory.systemTemp.createTemp(
      "codeflux_sync_limit_",
    );
    late OfflineDatabase database;
    addTearDown(() async {
      try {
        await database.close();
      } catch (_) {}
      if (await root.exists()) {
        await root.delete(recursive: true);
      }
    });

    database = await OfflineDatabase.openAt(
      p.join(root.path, "offline.sqlite3"),
      factory: databaseFactoryFfi,
    );
    final drafts = LocalDraftRepository(database);
    final queue = SyncQueueRepository(database);

    for (var index = 0; index < 3; index += 1) {
      final suffix = (index + 1).toString().padLeft(12, "0");
      final inspectionId = "23232323-2323-4232-8232-" + suffix;
      final operationId = "24242424-2424-4242-8242-" + suffix;
      await drafts.createInspection(
        id: inspectionId,
        officerUserId: "officer-1",
        productName: "Drain " + index.toString(),
      );
      await queue.enqueue(
        SyncOperation.queued(
          id: operationId,
          inspectionId: inspectionId,
          type: SyncOperationType.createInspection,
          resourceId: inspectionId,
          payload: <String, Object?>{
            "id": inspectionId,
            "product_name": "Drain " + index.toString(),
          },
        ),
      );
    }

    final service = OfflineSyncService(
      coordinator: SyncCoordinator(
        queue: queue,
        executor: SequenceExecutor(<String>{}),
      ),
      maxOperationsPerDrain: 2,
    );

    final summary = await service.drain(
      now: DateTime.utc(2026, 9, 24, 2),
    );

    expect(summary.processed, 2);
    expect(summary.synced, 2);
    expect(summary.limitReached, isTrue);
    expect(
      (await queue.listAll())
          .where((operation) => operation.state == SyncState.queued)
          .length,
      1,
    );
  });
}
