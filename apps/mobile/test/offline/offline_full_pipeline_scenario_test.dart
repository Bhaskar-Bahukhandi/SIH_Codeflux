import "dart:async";
import "dart:convert";
import "dart:io";
import "dart:typed_data";

import "package:flutter_test/flutter_test.dart";
import "package:http/http.dart" as http;
import "package:http/testing.dart";
import "package:path/path.dart" as p;
import "package:sqflite_common_ffi/sqflite_ffi.dart";

import "package:codeflux_mobile/offline/models/local_records.dart";
import "package:codeflux_mobile/offline/models/sync_state.dart";
import "package:codeflux_mobile/offline/persistence/local_draft_repository.dart";
import "package:codeflux_mobile/offline/persistence/offline_database.dart";
import "package:codeflux_mobile/offline/persistence/sync_queue_repository.dart";
import "package:codeflux_mobile/offline/storage/local_evidence_store.dart";
import "package:codeflux_mobile/offline/sync/codeflux_api_sync_adapter.dart";
import "package:codeflux_mobile/offline/sync/offline_sync_service.dart";
import "package:codeflux_mobile/offline/sync/sync_coordinator.dart";
import "package:codeflux_mobile/offline/sync/sync_operation_factory.dart";

const inspectionId = "81818181-8181-4818-8818-818181818181";
const frontCaptureId = "82828282-8282-4828-8828-828282828282";
const backCaptureId = "83838383-8383-4838-8838-838383838383";

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
    "two-capture offline pipeline drains in dependency order without duplicate OCR",
    () async {
      final root = await Directory.systemTemp.createTemp(
        "codeflux_full_pipeline_",
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
        } catch (_) {}
        if (await root.exists()) {
          await root.delete(recursive: true);
        }
      });

      var drafts = LocalDraftRepository(database);
      var queue = SyncQueueRepository(database);
      final factory = SyncOperationFactory();
      final baseTime = DateTime.utc(2026, 9, 24, 3);
      var offset = 0;
      DateTime nextTime() =>
          baseTime.add(Duration(seconds: offset++));

      final draft = await drafts.createInspection(
        id: inspectionId,
        officerUserId: "officer-1",
        productName: "Pipeline Product",
        productIdentifier: "PIPE-001",
        now: nextTime(),
      );

      Future<(LocalEvidenceRecord, StoredLocalEvidence)> registerEvidence({
        required String id,
        required String viewType,
        required List<int> bytes,
      }) async {
        final stored = await evidenceStore.persistBytes(
          inspectionId: inspectionId,
          evidenceId: id,
          bytes: Uint8List.fromList(bytes),
          originalFilename: viewType + ".jpg",
        );
        final record = await drafts.registerEvidence(
          id: id,
          inspectionId: inspectionId,
          viewType: viewType,
          localPath: stored.path,
          sha256: stored.sha256,
          sizeBytes: stored.sizeBytes,
          now: nextTime(),
        );
        return (record, stored);
      }

      final frontPair = await registerEvidence(
        id: frontCaptureId,
        viewType: "front",
        bytes: <int>[255, 216, 255, 224, 1, 2, 3, 4, 5],
      );
      final backPair = await registerEvidence(
        id: backCaptureId,
        viewType: "back",
        bytes: <int>[255, 216, 255, 224, 6, 7, 8, 9, 10],
      );
      final frontRecord = frontPair.$1;
      final backRecord = backPair.$1;

      const createOp = "84000000-0000-4400-8400-000000000001";
      const frontUploadOp = "84000000-0000-4400-8400-000000000002";
      const backUploadOp = "84000000-0000-4400-8400-000000000003";
      const frontProcessOp = "84000000-0000-4400-8400-000000000004";
      const backProcessOp = "84000000-0000-4400-8400-000000000005";
      const frontGeometryOp = "84000000-0000-4400-8400-000000000006";
      const backGeometryOp = "84000000-0000-4400-8400-000000000007";
      const frontOcrOp = "84000000-0000-4400-8400-000000000008";
      const backOcrOp = "84000000-0000-4400-8400-000000000009";
      const extractionOp = "84000000-0000-4400-8400-000000000010";
      const evaluationOp = "84000000-0000-4400-8400-000000000011";
      const submitOp = "84000000-0000-4400-8400-000000000012";

      const frontDerivativeId = "85000000-0000-4500-8500-000000000001";
      const backDerivativeId = "85000000-0000-4500-8500-000000000002";
      const frontQualityId = "85000000-0000-4500-8500-000000000003";
      const backQualityId = "85000000-0000-4500-8500-000000000004";
      const frontGeometryId = "85000000-0000-4500-8500-000000000005";
      const backGeometryId = "85000000-0000-4500-8500-000000000006";
      const frontCorrectedCandidate =
          "85000000-0000-4500-8500-000000000007";
      const backCorrectedCandidate =
          "85000000-0000-4500-8500-000000000008";
      const frontOcrRunId = "85000000-0000-4500-8500-000000000009";
      const backOcrRunId = "85000000-0000-4500-8500-000000000010";
      const extractionRunId = "85000000-0000-4500-8500-000000000011";
      const evaluationRunId = "85000000-0000-4500-8500-000000000012";

      await queue.enqueue(
        factory.createInspection(
          draft,
          operationId: createOp,
          now: nextTime(),
        ),
      );
      await queue.enqueue(
        factory.uploadCapture(
          frontRecord,
          createInspectionOperationId: createOp,
          operationId: frontUploadOp,
          now: nextTime(),
        ),
      );
      await queue.enqueue(
        factory.uploadCapture(
          backRecord,
          createInspectionOperationId: createOp,
          operationId: backUploadOp,
          now: nextTime(),
        ),
      );
      await queue.enqueue(
        factory.processCapture(
          inspectionId: inspectionId,
          captureId: frontCaptureId,
          derivativeId: frontDerivativeId,
          qualityAssessmentId: frontQualityId,
          dependencyIds: const <String>[frontUploadOp],
          operationId: frontProcessOp,
          now: nextTime(),
        ),
      );
      await queue.enqueue(
        factory.processCapture(
          inspectionId: inspectionId,
          captureId: backCaptureId,
          derivativeId: backDerivativeId,
          qualityAssessmentId: backQualityId,
          dependencyIds: const <String>[backUploadOp],
          operationId: backProcessOp,
          now: nextTime(),
        ),
      );
      await queue.enqueue(
        factory.analyzeGeometry(
          inspectionId: inspectionId,
          captureId: frontCaptureId,
          geometryAssessmentId: frontGeometryId,
          correctedDerivativeId: frontCorrectedCandidate,
          dependencyIds: const <String>[frontProcessOp],
          operationId: frontGeometryOp,
          now: nextTime(),
        ),
      );
      await queue.enqueue(
        factory.analyzeGeometry(
          inspectionId: inspectionId,
          captureId: backCaptureId,
          geometryAssessmentId: backGeometryId,
          correctedDerivativeId: backCorrectedCandidate,
          dependencyIds: const <String>[backProcessOp],
          operationId: backGeometryOp,
          now: nextTime(),
        ),
      );
      await queue.enqueue(
        factory.runOcr(
          inspectionId: inspectionId,
          captureId: frontCaptureId,
          ocrRunId: frontOcrRunId,
          dependencyIds: const <String>[frontGeometryOp],
          operationId: frontOcrOp,
          now: nextTime(),
        ),
      );
      await queue.enqueue(
        factory.runOcr(
          inspectionId: inspectionId,
          captureId: backCaptureId,
          ocrRunId: backOcrRunId,
          dependencyIds: const <String>[backGeometryOp],
          operationId: backOcrOp,
          now: nextTime(),
        ),
      );
      await queue.enqueue(
        factory.extractDeclarations(
          inspectionId: inspectionId,
          extractionRunId: extractionRunId,
          dependencyIds: const <String>[frontOcrOp, backOcrOp],
          operationId: extractionOp,
          now: nextTime(),
        ),
      );

      const context = <String, Object?>{
        "intended_for_retail_sale": true,
        "industrial_or_institutional_consumer": false,
        "package_exceeds_25kg_or_25l": false,
      };
      await queue.enqueue(
        factory.evaluateRules(
          inspectionId: inspectionId,
          evaluationRunId: evaluationRunId,
          context: context,
          dependencyIds: const <String>[extractionOp],
          operationId: evaluationOp,
          now: nextTime(),
        ),
      );
      await queue.enqueue(
        factory.submitInspection(
          inspectionId: inspectionId,
          dependencyIds: const <String>[evaluationOp],
          operationId: submitOp,
          now: nextTime(),
        ),
      );

      // App restart before any network work.
      await database.close();
      database = await OfflineDatabase.openAt(
        databasePath,
        factory: databaseFactoryFfi,
      );
      drafts = LocalDraftRepository(database);
      queue = SyncQueueRepository(database);

      final remoteCaptures = <String, Map<String, Object?>>{};
      final remoteOcr = <String, Map<String, Object?>>{};
      var inspectionCreates = 0;
      var captureUploads = 0;
      var preprocessingRuns = 0;
      var geometryRuns = 0;
      var ocrMutations = 0;
      var extractionRuns = 0;
      var evaluationRuns = 0;
      var submissions = 0;

      final client = MockClient.streaming((request, bodyStream) async {
        final path = request.url.path;
        expect(request.headers["authorization"], "Bearer pipeline-token");

        if (request.method == "POST" &&
            path == "/api/v1/inspections") {
          inspectionCreates += 1;
          final body = jsonDecode(
            utf8.decode(await bodyStream.toBytes()),
          ) as Map<String, dynamic>;
          return jsonResponse(<String, Object?>{
            "id": inspectionId,
            "product_name": body["product_name"],
            "product_identifier": body["product_identifier"],
            "status": "draft",
            "submitted_at": null,
            "reopened_for_recheck_at": null,
          }, 201);
        }

        if (request.method == "POST" &&
            path ==
                "/api/v1/inspections/" +
                    inspectionId +
                    "/captures") {
          captureUploads += 1;
          final multipart = latin1.decode(await bodyStream.toBytes());
          final isFront = multipart.contains(frontCaptureId);
          final captureId = isFront ? frontCaptureId : backCaptureId;
          final record = isFront ? frontPair.$2 : backPair.$2;
          final viewType = isFront ? "front" : "back";
          remoteCaptures[captureId] = <String, Object?>{
            "id": captureId,
            "inspection_id": inspectionId,
            "view_type": viewType,
            "sha256": record.sha256,
            "size_bytes": record.sizeBytes,
          };
          return jsonResponse(remoteCaptures[captureId], 201);
        }

        if (request.method == "POST" && path.endsWith("/process")) {
          preprocessingRuns += 1;
          final body = jsonDecode(
            utf8.decode(await bodyStream.toBytes()),
          ) as Map<String, dynamic>;
          final isFront = path.contains(frontCaptureId);
          final captureId = isFront ? frontCaptureId : backCaptureId;
          return jsonResponse(<String, Object?>{
            "derivative": <String, Object?>{
              "id": body["derivative_id"],
              "capture_id": captureId,
            },
            "quality": <String, Object?>{
              "id": body["quality_assessment_id"],
              "capture_id": captureId,
              "derivative_id": body["derivative_id"],
            },
          }, 200);
        }

        if (request.method == "POST" &&
            path.endsWith("/geometry/analyze")) {
          geometryRuns += 1;
          final body = jsonDecode(
            utf8.decode(await bodyStream.toBytes()),
          ) as Map<String, dynamic>;
          final isFront = path.contains(frontCaptureId);
          final captureId = isFront ? frontCaptureId : backCaptureId;
          return jsonResponse(<String, Object?>{
            "geometry": <String, Object?>{
              "id": body["geometry_assessment_id"],
              "capture_id": captureId,
              "corrected_derivative_id": null,
            },
            "corrected_derivative": null,
          }, 200);
        }

        if (request.method == "POST" && path.endsWith("/ocr/run")) {
          ocrMutations += 1;
          final body = jsonDecode(
            utf8.decode(await bodyStream.toBytes()),
          ) as Map<String, dynamic>;
          final isFront = path.contains(frontCaptureId);
          final captureId = isFront ? frontCaptureId : backCaptureId;
          final runId = body["id"]!.toString();
          remoteOcr[runId] = <String, Object?>{
            "run": <String, Object?>{
              "id": runId,
              "capture_id": captureId,
            },
            "blocks": <Object?>[],
          };

          if (isFront) {
            throw TimeoutException(
              "Simulated lost OCR response after remote commit.",
            );
          }
          return jsonResponse(remoteOcr[runId], 200);
        }

        if (request.method == "GET" && path.contains("/ocr/runs/")) {
          final runId = path.split("/").last;
          final result = remoteOcr[runId];
          return result == null
              ? jsonResponse(<String, Object?>{
                  "error": <String, Object?>{
                    "code": "capture_ocr_not_found",
                    "message": "Not found.",
                  },
                }, 404)
              : jsonResponse(result, 200);
        }

        if (request.method == "POST" &&
            path.endsWith("/declarations/extract")) {
          extractionRuns += 1;
          final body = jsonDecode(
            utf8.decode(await bodyStream.toBytes()),
          ) as Map<String, dynamic>;
          return jsonResponse(<String, Object?>{
            "run": <String, Object?>{
              "id": body["id"],
              "inspection_id": inspectionId,
            },
            "observations": <Object?>[],
            "summaries": <Object?>[],
          }, 200);
        }

        if (request.method == "POST" &&
            path.endsWith("/rule-evaluations/evaluate")) {
          evaluationRuns += 1;
          final body = jsonDecode(
            utf8.decode(await bodyStream.toBytes()),
          ) as Map<String, dynamic>;
          return jsonResponse(<String, Object?>{
            "run": <String, Object?>{
              "id": body["id"],
              "inspection_id": inspectionId,
              "context_snapshot": body["context"],
            },
            "results": <Object?>[],
          }, 200);
        }

        if (request.method == "POST" && path.endsWith("/submit")) {
          submissions += 1;
          return jsonResponse(<String, Object?>{
            "id": inspectionId,
            "status": "pending_review",
            "submitted_at": "2026-09-24T03:30:00Z",
            "reopened_for_recheck_at": null,
          }, 200);
        }

        return jsonResponse(<String, Object?>{
          "error": <String, Object?>{
            "code": "unexpected_test_route",
            "message": request.method + " " + path,
          },
        }, 500);
      });

      final adapter = CodefluxApiSyncAdapter(
        client: client,
        serverBaseUri: Uri.parse("https://example.test/"),
        accessTokenProvider: () async => "pipeline-token",
      );
      final service = OfflineSyncService(
        coordinator: SyncCoordinator(
          queue: queue,
          executor: adapter,
          reconciler: adapter,
        ),
      );

      final summary = await service.drain(
        now: DateTime.utc(2026, 9, 24, 4),
      );

      expect(summary.processed, 12);
      expect(summary.synced, 12);
      expect(summary.blocked, 0);
      expect(summary.conflicts, 0);
      expect(summary.reconciliationRequired, 0);
      expect(summary.limitReached, isFalse);

      expect(inspectionCreates, 1);
      expect(captureUploads, 2);
      expect(preprocessingRuns, 2);
      expect(geometryRuns, 2);
      expect(ocrMutations, 2);
      expect(extractionRuns, 1);
      expect(evaluationRuns, 1);
      expect(submissions, 1);

      final all = await queue.listAll();
      expect(all.length, 12);
      expect(
        all.every((operation) => operation.state == SyncState.synced),
        isTrue,
      );

      expect(
        (await drafts.getInspection(inspectionId))!.syncState,
        SyncState.synced,
      );
      expect(await evidenceStore.verify(frontPair.$2), isTrue);
      expect(await evidenceStore.verify(backPair.$2), isTrue);

      final secondDrain = await service.drain(
        now: DateTime.utc(2026, 9, 24, 4, 1),
      );
      expect(secondDrain.processed, 0);
      expect(inspectionCreates, 1);
      expect(captureUploads, 2);
      expect(ocrMutations, 2);

      await database.close();
      database = await OfflineDatabase.openAt(
        databasePath,
        factory: databaseFactoryFfi,
      );
      queue = SyncQueueRepository(database);
      final persisted = await queue.listAll();
      expect(persisted.length, 12);
      expect(
        persisted.every(
          (operation) => operation.state == SyncState.synced,
        ),
        isTrue,
      );
    },
  );
}
