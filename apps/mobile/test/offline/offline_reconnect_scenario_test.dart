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
const frontEvidenceId = "14141414-1414-4414-8414-141414141414";
const detailEvidenceId = "14141414-1414-4414-8414-151515151515";
const inspectionOperationId = "15151515-1515-4515-8515-151515151515";
const frontOperationId = "16161616-1616-4616-8616-161616161616";
const detailOperationId = "16161616-1616-4616-8616-171717171717";

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
    "multiple offline captures survive restart and reconnect exactly once",
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
        officerUserId: "officer-1",
        productName: "Offline Reconnect Product",
        productIdentifier: "OFFLINE-001",
        now: DateTime.utc(2026, 9, 23, 23),
      );

      final frontEvidence = await evidenceStore.persistBytes(
        inspectionId: inspectionId,
        evidenceId: frontEvidenceId,
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
      final detailEvidence = await evidenceStore.persistBytes(
        inspectionId: inspectionId,
        evidenceId: detailEvidenceId,
        bytes: Uint8List.fromList(<int>[
          255,
          216,
          255,
          224,
          7,
          8,
          9,
          10,
          11,
          12,
        ]),
        originalFilename: "detail.jpg",
      );

      final frontRecord = await drafts.registerEvidence(
        id: frontEvidenceId,
        inspectionId: inspectionId,
        viewType: "front",
        localPath: frontEvidence.path,
        sha256: frontEvidence.sha256,
        sizeBytes: frontEvidence.sizeBytes,
        now: DateTime.utc(2026, 9, 23, 23, 0, 1),
      );
      final detailRecord = await drafts.registerEvidence(
        id: detailEvidenceId,
        inspectionId: inspectionId,
        viewType: "detail",
        localPath: detailEvidence.path,
        sha256: detailEvidence.sha256,
        sizeBytes: detailEvidence.sizeBytes,
        now: DateTime.utc(2026, 9, 23, 23, 0, 2),
      );

      await queue.enqueue(
        operationFactory.createInspection(
          draft,
          operationId: inspectionOperationId,
          now: DateTime.utc(2026, 9, 23, 23, 0, 3),
        ),
      );
      await queue.enqueue(
        operationFactory.uploadCapture(
          frontRecord,
          createInspectionOperationId: inspectionOperationId,
          operationId: frontOperationId,
          now: DateTime.utc(2026, 9, 23, 23, 0, 4),
        ),
      );
      await queue.enqueue(
        operationFactory.uploadCapture(
          detailRecord,
          createInspectionOperationId: inspectionOperationId,
          operationId: detailOperationId,
          now: DateTime.utc(2026, 9, 23, 23, 0, 5),
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
      final reopenedFront = await drafts.getEvidence(frontEvidenceId);
      final reopenedDetail = await drafts.getEvidence(detailEvidenceId);
      expect(reopenedDraft, isNotNull);
      expect(reopenedFront, isNotNull);
      expect(reopenedDetail, isNotNull);
      expect(reopenedDraft!.syncState, SyncState.queued);
      expect(reopenedFront!.syncState, SyncState.queued);
      expect(reopenedDetail!.syncState, SyncState.queued);
      expect(await evidenceStore.verify(frontEvidence), isTrue);
      expect(await evidenceStore.verify(detailEvidence), isTrue);
      expect((await queue.listAll()).length, 3);

      final remoteInspections = <String, Map<String, Object?>>{};
      final remoteCaptures = <String, Map<String, Object?>>{};
      var inspectionMutationCount = 0;
      var frontMutationCount = 0;
      var detailMutationCount = 0;

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
          final multipartBody = latin1.decode(
            await bodyStream.toBytes(),
          );

          if (multipartBody.contains(frontEvidenceId)) {
            frontMutationCount += 1;
            remoteCaptures[frontEvidenceId] = <String, Object?>{
              "id": frontEvidenceId,
              "inspection_id": inspectionId,
              "view_type": "front",
              "sha256": frontEvidence.sha256,
              "size_bytes": frontEvidence.sizeBytes,
            };
            return jsonResponse(remoteCaptures[frontEvidenceId], 201);
          }

          if (multipartBody.contains(detailEvidenceId)) {
            // The server applies the second capture, but the response is lost.
            detailMutationCount += 1;
            remoteCaptures[detailEvidenceId] = <String, Object?>{
              "id": detailEvidenceId,
              "inspection_id": inspectionId,
              "view_type": "detail",
              "sha256": detailEvidence.sha256,
              "size_bytes": detailEvidence.sizeBytes,
            };
            throw TimeoutException(
              "Simulated lost response after detail capture commit.",
            );
          }

          return jsonResponse(
            <String, Object?>{
              "error": <String, Object?>{
                "code": "unexpected_capture",
                "message": "Unknown capture ID in multipart body.",
              },
            },
            422,
          );
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
      expect(frontMutationCount, 0);
      expect(detailMutationCount, 0);

      final frontSync = await coordinator.runNext(
        now: DateTime.utc(2026, 9, 23, 23, 10, 1),
      );
      expect(frontSync.status, SyncCycleStatus.synced);
      expect(frontMutationCount, 1);
      expect(detailMutationCount, 0);

      final detailSync = await coordinator.runNext(
        now: DateTime.utc(2026, 9, 23, 23, 10, 2),
      );
      expect(detailSync.status, SyncCycleStatus.synced);
      expect(detailMutationCount, 1);
      expect(remoteCaptures.length, 2);

      // Re-running synchronization after the lost response must do nothing.
      final replay = await coordinator.runNext(
        now: DateTime.utc(2026, 9, 23, 23, 11),
      );
      expect(replay.status, SyncCycleStatus.idle);
      expect(inspectionMutationCount, 1);
      expect(frontMutationCount, 1);
      expect(detailMutationCount, 1);
      expect(remoteInspections.length, 1);
      expect(remoteCaptures.length, 2);

      final operations = await queue.listAll();
      expect(operations.length, 3);
      expect(
        operations.every((operation) => operation.state == SyncState.synced),
        isTrue,
      );

      final syncedDraft = await drafts.getInspection(inspectionId);
      final syncedFront = await drafts.getEvidence(frontEvidenceId);
      final syncedDetail = await drafts.getEvidence(detailEvidenceId);
      expect(syncedDraft!.syncState, SyncState.synced);
      expect(syncedDraft.remoteId, inspectionId);
      expect(syncedFront!.syncState, SyncState.synced);
      expect(syncedFront.remoteId, frontEvidenceId);
      expect(syncedDetail!.syncState, SyncState.synced);
      expect(syncedDetail.remoteId, detailEvidenceId);

      // Synchronization alone never deletes the Officer's local originals.
      expect(await evidenceStore.verify(frontEvidence), isTrue);
      expect(await evidenceStore.verify(detailEvidence), isTrue);

      // A second application restart must retain terminal queue state.
      await database.close();
      database = await OfflineDatabase.openAt(
        databasePath,
        factory: databaseFactoryFfi,
      );
      queue = SyncQueueRepository(database);

      final persistedOperations = await queue.listAll();
      expect(persistedOperations.length, 3);
      expect(
        persistedOperations.every(
          (operation) => operation.state == SyncState.synced,
        ),
        isTrue,
      );
      expect(await queue.claimNextReady(DateTime.utc(2026, 9, 24)), isNull);
      expect(inspectionMutationCount, 1);
      expect(frontMutationCount, 1);
      expect(detailMutationCount, 1);
    },
  );
}
