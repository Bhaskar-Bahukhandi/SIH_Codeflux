import "dart:async";
import "dart:convert";
import "dart:io";
import "dart:typed_data";

import "package:flutter_test/flutter_test.dart";
import "package:http/http.dart" as http;
import "package:http/testing.dart";
import "package:path/path.dart" as p;
import "package:sqflite_common_ffi/sqflite_ffi.dart";

import "package:codeflux_mobile/offline/models/sync_state.dart";
import "package:codeflux_mobile/offline/persistence/local_draft_repository.dart";
import "package:codeflux_mobile/offline/persistence/offline_database.dart";
import "package:codeflux_mobile/offline/persistence/sync_queue_repository.dart";
import "package:codeflux_mobile/offline/storage/local_evidence_store.dart";
import "package:codeflux_mobile/offline/sync/codeflux_api_sync_adapter.dart";
import "package:codeflux_mobile/offline/sync/sync_coordinator.dart";
import "package:codeflux_mobile/offline/sync/sync_operation_factory.dart";

const inspectionId = "13131313-1313-4313-8313-131313131313";
const evidenceId = "14141414-1414-4414-8414-141414141414";
const inspectionOperationId = "15151515-1515-4515-8515-151515151515";
const captureOperationId = "16161616-1616-4616-8616-161616161616";

http.StreamedResponse jsonResponse(Object? body, int statusCode) {
  return http.StreamedResponse(
    Stream<List<int>>.value(utf8.encode(jsonEncode(body))),
    statusCode,
    headers: const <String, String>{
      "content-type": "application/json",
    },
  );
}

void main() {
  setUpAll(() {
    sqfliteFfiInit();
  });

  test(
    "offline draft survives restart and reconnect applies each mutation once",
    () async {
      final root = await Directory.systemTemp.createTemp(
        "codeflux_offline_reconnect_",
      );

      final databasePath = p.join(root.path, "offline.sqlite3");
      final evidenceStore = LocalEvidenceStore(
        Directory(p.join(root.path, "evidence")),
      );

      var database = await OfflineDatabase.openAt(
        databasePath,
        factory: databaseFactoryFfi,
      );
      addTearDown(() async {
        try {
          await database.close();
        } catch (_) {
          // The scenario intentionally closes/reopens the database.
        }
        if (await root.exists()) {
          await root.delete(recursive: true);
        }
      });

      var drafts = LocalDraftRepository(database);
      var queue = SyncQueueRepository(database);
      final operationFactory = SyncOperationFactory();

      final draft = await drafts.createInspection(
        id: inspectionId,
        productName: "Offline Reconnect Product",
        productIdentifier: "OFFLINE-001",
        now: DateTime.utc(2026, 9, 23, 23),
      );

      final localEvidence = await evidenceStore.persistBytes(
        inspectionId: inspectionId,
        evidenceId: evidenceId,
        bytes: Uint8List.fromList(<int>[
          255,
          216,
          255,
          224,
          1,
          2,
          3,
          4,
          5,
          6,
        ]),
        originalFilename: "front.jpg",
      );

      final evidence = await drafts.registerEvidence(
        id: evidenceId,
        inspectionId: inspectionId,
        viewType: "front",
        localPath: localEvidence.path,
        sha256: localEvidence.sha256,
        sizeBytes: localEvidence.sizeBytes,
        now: DateTime.utc(2026, 9, 23, 23, 0, 1),
      );

      await queue.enqueue(
        operationFactory.createInspection(
          draft,
          operationId: inspectionOperationId,
          now: DateTime.utc(2026, 9, 23, 23, 0, 2),
        ),
      );
      await queue.enqueue(
        operationFactory.uploadCapture(
          evidence,
          createInspectionOperationId: inspectionOperationId,
          operationId: captureOperationId,
          now: DateTime.utc(2026, 9, 23, 23, 0, 3),
        ),
      );

      // Simulate the Officer closing/restarting the app while still offline.
      await database.close();

      database = await OfflineDatabase.openAt(
        databasePath,
        factory: databaseFactoryFfi,
      );
      drafts = LocalDraftRepository(database);
      queue = SyncQueueRepository(database);
      final reopenedDraft = await drafts.getInspection(inspectionId);
      final reopenedEvidence = await drafts.getEvidence(evidenceId);
      expect(reopenedDraft, isNotNull);
      expect(reopenedEvidence, isNotNull);
      expect(reopenedDraft!.syncState, SyncState.queued);
      expect(reopenedEvidence!.syncState, SyncState.queued);
      expect(await evidenceStore.verify(localEvidence), isTrue);
      expect((await queue.listAll()).length, 2);

      final remoteInspections = <String, Map<String, Object?>>{};
      final remoteCaptures = <String, Map<String, Object?>>{};
      var inspectionMutationCount = 0;
      var captureMutationCount = 0;

      final client = MockClient.streaming((request, bodyStream) async {
        expect(request.headers["authorization"], "Bearer reconnect-token");

        if (request.method == "POST" &&
            request.url.path == "/api/v1/inspections") {
          final body = jsonDecode(
            utf8.decode(await bodyStream.toBytes()),
          ) as Map<String, dynamic>;
          inspectionMutationCount += 1;
          remoteInspections[inspectionId] = <String, Object?>{
            "id": body["id"],
            "product_name": body["product_name"],
            "product_identifier": body["product_identifier"],
          };
          return jsonResponse(remoteInspections[inspectionId], 201);
        }

        if (request.method == "POST" &&
            request.url.path ==
                "/api/v1/inspections/" +
                    inspectionId +
                    "/captures") {
          // The server applies the mutation, but the response is lost.
          await bodyStream.toBytes();
          captureMutationCount += 1;
          remoteCaptures[evidenceId] = <String, Object?>{
            "id": evidenceId,
            "inspection_id": inspectionId,
            "view_type": "front",
            "sha256": localEvidence.sha256,
            "size_bytes": localEvidence.sizeBytes,
          };
          throw TimeoutException("Simulated lost capture response.");
        }

        if (request.method == "GET" &&
            request.url.path ==
                "/api/v1/inspections/" +
                    inspectionId +
                    "/captures") {
          return jsonResponse(remoteCaptures.values.toList(), 200);
        }

        if (request.method == "GET" &&
            request.url.path ==
                "/api/v1/inspections/" + inspectionId) {
          final inspection = remoteInspections[inspectionId];
          if (inspection == null) {
            return jsonResponse(
              <String, Object?>{
                "error": <String, Object?>{
                  "code": "inspection_not_found",
                  "message": "Inspection not found.",
                },
              },
              404,
            );
          }
          return jsonResponse(inspection, 200);
        }

        return jsonResponse(
          <String, Object?>{
            "error": <String, Object?>{
              "code": "unexpected_test_route",
              "message": request.method + " " + request.url.path,
            },
          },
          500,
        );
      });

      final adapter = CodefluxApiSyncAdapter(
        client: client,
        serverBaseUri: Uri.parse("https://example.test/"),
        accessTokenProvider: () async => "reconnect-token",
      );
      final coordinator = SyncCoordinator(
        queue: queue,
        executor: adapter,
        reconciler: adapter,
      );

      final inspectionSync = await coordinator.runNext(
        now: DateTime.utc(2026, 9, 23, 23, 10),
      );
      expect(inspectionSync.status, SyncCycleStatus.synced);
      expect(inspectionMutationCount, 1);
      expect(captureMutationCount, 0);

      final captureSync = await coordinator.runNext(
        now: DateTime.utc(2026, 9, 23, 23, 10, 1),
      );
      expect(captureSync.status, SyncCycleStatus.synced);
      expect(captureMutationCount, 1);
      expect(remoteCaptures.length, 1);

      // Re-running synchronization after the lost response must do nothing.
      final replay = await coordinator.runNext(
        now: DateTime.utc(2026, 9, 23, 23, 11),
      );
      expect(replay.status, SyncCycleStatus.idle);
      expect(inspectionMutationCount, 1);
      expect(captureMutationCount, 1);
      expect(remoteInspections.length, 1);
      expect(remoteCaptures.length, 1);

      final operations = await queue.listAll();
      expect(operations.length, 2);
      expect(
        operations.every((operation) => operation.state == SyncState.synced),
        isTrue,
      );
      final syncedDraft = await drafts.getInspection(inspectionId);
      final syncedEvidence = await drafts.getEvidence(evidenceId);
      expect(syncedDraft!.syncState, SyncState.synced);
      expect(syncedDraft.remoteId, inspectionId);
      expect(syncedEvidence!.syncState, SyncState.synced);
      expect(syncedEvidence.remoteId, evidenceId);

      // Synchronization alone never deletes the Officer's local original.
      expect(await evidenceStore.verify(localEvidence), isTrue);

      // A second application restart must retain the terminal queue state.
      await database.close();
      database = await OfflineDatabase.openAt(
        databasePath,
        factory: databaseFactoryFfi,
      );
      queue = SyncQueueRepository(database);

      final persistedOperations = await queue.listAll();
      expect(persistedOperations.length, 2);
      expect(
        persistedOperations.every(
          (operation) => operation.state == SyncState.synced,
        ),
        isTrue,
      );
      expect(await queue.claimNextReady(DateTime.utc(2026, 9, 24)), isNull);
      expect(inspectionMutationCount, 1);
      expect(captureMutationCount, 1);
    },
  );
}
