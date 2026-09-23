import "dart:io";

import "package:flutter_test/flutter_test.dart";
import "package:path/path.dart" as p;
import "package:sqflite_common_ffi/sqflite_ffi.dart";

import "package:codeflux_mobile/offline/models/sync_operation.dart";
import "package:codeflux_mobile/offline/models/sync_state.dart";
import "package:codeflux_mobile/offline/persistence/local_draft_repository.dart";
import "package:codeflux_mobile/offline/persistence/offline_database.dart";
import "package:codeflux_mobile/offline/persistence/sync_queue_repository.dart";
import "package:codeflux_mobile/offline/sync/failure_classifier.dart";
import "package:codeflux_mobile/offline/sync/retry_policy.dart";

const inspectionId = "11111111-1111-4111-8111-111111111111";
const createOperationId = "22222222-2222-4222-8222-222222222222";
const captureOperationId = "33333333-3333-4333-8333-333333333333";
const captureId = "44444444-4444-4444-8444-444444444444";

void main() {
  late Directory tempDirectory;
  late String databasePath;
  late OfflineDatabase offlineDatabase;
  late LocalDraftRepository drafts;
  late SyncQueueRepository queue;

  setUpAll(() {
    sqfliteFfiInit();
  });

  setUp(() async {
    tempDirectory = await Directory.systemTemp.createTemp(
      "codeflux_queue_test_",
    );
    databasePath = p.join(tempDirectory.path, "offline.sqlite3");
    offlineDatabase = await OfflineDatabase.openAt(
      databasePath,
      factory: databaseFactoryFfi,
    );
    drafts = LocalDraftRepository(offlineDatabase);
    queue = SyncQueueRepository(offlineDatabase);
    await drafts.createInspection(
      id: inspectionId,
      officerUserId: "officer-1",
      productName: "Offline Test Product",
      now: DateTime.utc(2026, 9, 23, 10),
    );
    await drafts.registerEvidence(
      id: captureId,
      inspectionId: inspectionId,
      viewType: "front",
      localPath: "/test/front.jpg",
      sha256:
          "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      sizeBytes: 123,
      now: DateTime.utc(2026, 9, 23, 10, 0, 1),
    );
  });

  tearDown(() async {
    await offlineDatabase.close();
    if (await tempDirectory.exists()) {
      await tempDirectory.delete(recursive: true);
    }
  });

  SyncOperation createOperation(DateTime now) {
    return SyncOperation.queued(
      id: createOperationId,
      inspectionId: inspectionId,
      type: SyncOperationType.createInspection,
      resourceId: inspectionId,
      payload: const <String, Object?>{
        "id": inspectionId,
        "product_name": "Offline Test Product",
      },
      now: now,
    );
  }

  SyncOperation captureOperation(DateTime now) {
    return SyncOperation.queued(
      id: captureOperationId,
      inspectionId: inspectionId,
      type: SyncOperationType.uploadCapture,
      resourceId: captureId,
      payload: const <String, Object?>{
        "capture_id": captureId,
        "view_type": "front",
        "sha256": "abc123",
      },
      dependencyIds: const <String>[createOperationId],
      now: now.add(const Duration(seconds: 1)),
    );
  }

  test("dependency order prevents capture sync before inspection", () async {
    final now = DateTime.utc(2026, 9, 23, 10, 30);
    await queue.enqueue(createOperation(now));
    expect(
      (await drafts.getInspection(inspectionId))!.syncState,
      SyncState.queued,
    );

    await queue.enqueue(captureOperation(now));
    expect(
      (await drafts.getEvidence(captureId))!.syncState,
      SyncState.queued,
    );

    final initiallyQueued = await queue.inspectionSyncSummary(inspectionId);
    expect(initiallyQueued.overallState, SyncState.queued);
    expect(initiallyQueued.totalOperations, 2);
    expect(initiallyQueued.isFullySynced, isFalse);

    final first = await queue.claimNextReady(now.add(const Duration(seconds: 2)));
    expect(first, isNotNull);
    expect(first!.id, createOperationId);
    expect(first.state, SyncState.syncing);
    expect(first.attemptCount, 1);
    expect(
      (await drafts.getInspection(inspectionId))!.syncState,
      SyncState.syncing,
    );

    await queue.markSynced(
      createOperationId,
      remoteResourceId: inspectionId,
      now: now.add(const Duration(seconds: 3)),
    );
    final syncedInspection = await drafts.getInspection(inspectionId);
    expect(syncedInspection!.syncState, SyncState.synced);
    expect(syncedInspection.remoteId, inspectionId);

    final partiallySynced = await queue.inspectionSyncSummary(inspectionId);
    expect(partiallySynced.localResourceState, SyncState.synced);
    expect(partiallySynced.overallState, SyncState.queued);
    expect(partiallySynced.isFullySynced, isFalse);

    final second = await queue.claimNextReady(now.add(const Duration(seconds: 4)));
    expect(second, isNotNull);
    expect(second!.id, captureOperationId);
    expect(second.state, SyncState.syncing);
    expect(
      (await drafts.getEvidence(captureId))!.syncState,
      SyncState.syncing,
    );
    expect(
      (await queue.inspectionSyncSummary(inspectionId)).overallState,
      SyncState.syncing,
    );

    await queue.markSynced(
      captureOperationId,
      remoteResourceId: captureId,
      now: now.add(const Duration(seconds: 5)),
    );
    final fullySynced = await queue.inspectionSyncSummary(inspectionId);
    expect(fullySynced.overallState, SyncState.synced);
    expect(fullySynced.isFullySynced, isTrue);
    expect(fullySynced.count(SyncState.synced), 2);
  });

  test("blocked predecessor explicitly blocks dependent work", () async {
    final now = DateTime.utc(2026, 9, 23, 11);
    await queue.enqueue(createOperation(now));
    await queue.enqueue(captureOperation(now));

    final first = await queue.claimNextReady(now.add(const Duration(seconds: 2)));
    expect(first!.id, createOperationId);

    await queue.markFailure(
      createOperationId,
      decision: SyncFailureClassifier.classify(
        statusCode: 409,
        apiCode: "client_resource_id_conflict",
      ),
      retryPolicy: const SyncRetryPolicy(),
      apiCode: "client_resource_id_conflict",
      now: now.add(const Duration(seconds: 3)),
    );

    final next = await queue.claimNextReady(now.add(const Duration(seconds: 4)));
    expect(next, isNull);

    final dependent = await queue.getById(captureOperationId);
    expect(dependent!.state, SyncState.blocked);
    expect(dependent.lastErrorKind, "dependency_blocked");
    expect(
      (await drafts.getInspection(inspectionId))!.syncState,
      SyncState.conflict,
    );
    expect(
      (await drafts.getEvidence(captureId))!.syncState,
      SyncState.blocked,
    );
  });

  test("timeout outcome requires reconciliation before sync completion", () async {
    final now = DateTime.utc(2026, 9, 23, 12);
    await queue.enqueue(createOperation(now));

    final claimed = await queue.claimNextReady(now);
    expect(claimed!.state, SyncState.syncing);

    await queue.markFailure(
      createOperationId,
      decision: SyncFailureClassifier.classify(timedOut: true),
      retryPolicy: const SyncRetryPolicy(),
      now: now.add(const Duration(seconds: 1)),
    );

    final pending = await queue.getById(createOperationId);
    expect(pending!.state, SyncState.retryRequired);
    expect(pending.nextAttemptAt, isNull);

    final blindReplay = await queue.claimNextReady(
      now.add(const Duration(hours: 1)),
    );
    expect(blindReplay, isNull);

    await queue.markSynced(
      createOperationId,
      remoteResourceId: inspectionId,
      reconciledAfterUnknownOutcome: true,
      now: now.add(const Duration(hours: 1, seconds: 1)),
    );
    expect(
      (await queue.getById(createOperationId))!.state,
      SyncState.synced,
    );
  });

  test("transport failure uses bounded delayed retry", () async {
    final now = DateTime.utc(2026, 9, 23, 13);
    await queue.enqueue(createOperation(now));
    await queue.claimNextReady(now);

    await queue.markFailure(
      createOperationId,
      decision: SyncFailureClassifier.classify(
        transportUnavailable: true,
      ),
      retryPolicy: const SyncRetryPolicy(),
      now: now,
    );

    final failed = await queue.getById(createOperationId);
    expect(failed!.state, SyncState.retryRequired);
    expect(
      failed.nextAttemptAt,
      now.add(const Duration(seconds: 5)),
    );

    expect(
      await queue.claimNextReady(now.add(const Duration(seconds: 4))),
      isNull,
    );
    final retried = await queue.claimNextReady(
      now.add(const Duration(seconds: 5)),
    );
    expect(retried, isNotNull);
    expect(retried!.attemptCount, 2);
  });

  test("interrupted sync is parked until remote outcome is reconciled", () async {
    final now = DateTime.utc(2026, 9, 23, 14);
    await queue.enqueue(createOperation(now));
    final claimed = await queue.claimNextReady(now);
    expect(claimed!.state, SyncState.syncing);

    await offlineDatabase.close();
    offlineDatabase = await OfflineDatabase.openAt(
      databasePath,
      factory: databaseFactoryFfi,
    );
    drafts = LocalDraftRepository(offlineDatabase);
    queue = SyncQueueRepository(offlineDatabase);

    final recoveryTime = now.add(const Duration(minutes: 1));
    expect(
      await queue.recoverInterruptedSyncs(now: recoveryTime),
      1,
    );

    final recovered = await queue.getById(createOperationId);
    expect(recovered!.state, SyncState.retryRequired);
    expect(
      recovered.lastErrorKind,
      "process_interrupted_outcome_unknown",
    );
    expect(recovered.nextAttemptAt, isNull);
    expect(
      (await drafts.getInspection(inspectionId))!.syncState,
      SyncState.retryRequired,
    );

    final parked = await queue.listReconciliationRequired();
    expect(parked.map((operation) => operation.id), contains(createOperationId));

    final blindReplay = await queue.claimNextReady(
      recoveryTime.add(const Duration(hours: 1)),
    );
    expect(blindReplay, isNull);
  });

  test("local enqueue replay is idempotent but changed payload is rejected", () async {
    final now = DateTime.utc(2026, 9, 23, 15);
    final original = createOperation(now);
    final first = await queue.enqueue(original);
    final replay = await queue.enqueue(original);

    expect(first.id, replay.id);
    expect((await queue.listAll()).length, 1);

    final changed = SyncOperation.queued(
      id: createOperationId,
      inspectionId: inspectionId,
      type: SyncOperationType.createInspection,
      resourceId: inspectionId,
      payload: const <String, Object?>{
        "id": inspectionId,
        "product_name": "Different Product",
      },
      now: now,
    );

    await expectLater(
      queue.enqueue(changed),
      throwsA(isA<StateError>()),
    );
  });
}
