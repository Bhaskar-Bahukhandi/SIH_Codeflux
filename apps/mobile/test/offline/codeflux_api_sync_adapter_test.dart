import "dart:convert";
import "dart:io";
import "dart:typed_data";

import "package:crypto/crypto.dart";
import "package:flutter_test/flutter_test.dart";
import "package:http/http.dart" as http;
import "package:http/testing.dart";
import "package:path/path.dart" as p;

import "package:codeflux_mobile/offline/models/sync_operation.dart";
import "package:codeflux_mobile/offline/sync/codeflux_api_sync_adapter.dart";
import "package:codeflux_mobile/offline/sync/sync_coordinator.dart";

const inspectionId = "77777777-7777-4777-8777-777777777777";
const captureId = "88888888-8888-4888-8888-888888888888";

void main() {
  test("inspection execution sends stable ID and auth token", () async {
    final client = MockClient((request) async {
      expect(request.method, "POST");
      expect(request.url.path, "/api/v1/inspections");
      expect(request.headers["authorization"], "Bearer token-123");

      final body = jsonDecode(request.body) as Map<String, dynamic>;
      expect(body["id"], inspectionId);
      expect(body["product_name"], "Offline Product");

      return http.Response(
        jsonEncode(<String, Object?>{
          "id": inspectionId,
          "product_name": "Offline Product",
          "product_identifier": null,
        }),
        201,
        headers: <String, String>{"content-type": "application/json"},
      );
    });

    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token-123",
    );
    final operation = SyncOperation.queued(
      id: "op-inspection",
      inspectionId: inspectionId,
      type: SyncOperationType.createInspection,
      resourceId: inspectionId,
      payload: const <String, Object?>{
        "id": inspectionId,
        "product_name": "Offline Product",
        "product_identifier": null,
      },
    );

    final result = await adapter.execute(operation);
    expect(result.remoteResourceId, inspectionId);
  });

  test("inspection reconciliation distinguishes applied from absent", () async {
    var exists = true;
    final client = MockClient((request) async {
      expect(request.method, "GET");
      if (!exists) {
        return http.Response(
          jsonEncode(<String, Object?>{
            "error": <String, Object?>{
              "code": "inspection_not_found",
              "message": "Inspection not found.",
            },
          }),
          404,
        );
      }
      return http.Response(
        jsonEncode(<String, Object?>{
          "id": inspectionId,
          "product_name": "Offline Product",
          "product_identifier": null,
        }),
        200,
      );
    });

    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-inspection",
      inspectionId: inspectionId,
      type: SyncOperationType.createInspection,
      resourceId: inspectionId,
      payload: const <String, Object?>{
        "id": inspectionId,
        "product_name": "Offline Product",
        "product_identifier": null,
      },
    );

    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.applied,
    );

    exists = false;
    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.notApplied,
    );
  });

  test("capture upload validates local bytes before multipart send", () async {
    final tempDirectory = await Directory.systemTemp.createTemp(
      "codeflux_api_adapter_",
    );
    addTearDown(() async {
      if (await tempDirectory.exists()) {
        await tempDirectory.delete(recursive: true);
      }
    });

    final bytes = Uint8List.fromList(<int>[1, 2, 3, 4, 5, 6]);
    final file = File(p.join(tempDirectory.path, "front.jpg"));
    await file.writeAsBytes(bytes);
    final digest = sha256.convert(bytes).toString();

    var calls = 0;
    final client = MockClient.streaming((request, bodyStream) async {
      calls += 1;
      expect(request.method, "POST");
      expect(
        request.url.path,
        "/api/v1/inspections/" + inspectionId + "/captures",
      );
      expect(request.headers["authorization"], "Bearer token");

      expect(
        request.headers["content-type"],
        startsWith("multipart/form-data;"),
      );
      final encodedBody = latin1.decode(await bodyStream.toBytes());
      expect(encodedBody, contains('name="capture_id"'));
      expect(encodedBody, contains(captureId));
      expect(encodedBody, contains('name="view_type"'));
      expect(encodedBody, contains("front"));
      expect(encodedBody, contains('filename="front.jpg"'));

      return http.StreamedResponse(
        Stream<List<int>>.value(
          utf8.encode(
            jsonEncode(<String, Object?>{
              "id": captureId,
              "inspection_id": inspectionId,
              "view_type": "front",
              "sha256": digest,
              "size_bytes": bytes.length,
            }),
          ),
        ),
        201,
        headers: <String, String>{"content-type": "application/json"},
      );
    });

    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-capture",
      inspectionId: inspectionId,
      type: SyncOperationType.uploadCapture,
      resourceId: captureId,
      payload: <String, Object?>{
        "capture_id": captureId,
        "view_type": "front",
        "local_path": file.path,
        "sha256": digest,
        "size_bytes": bytes.length,
      },
    );

    final result = await adapter.execute(operation);
    expect(result.remoteResourceId, captureId);
    expect(calls, 1);
  });

  test("submission execution and reconciliation verify lifecycle state", () async {
    var status = "pending_review";
    String? reopenedAt;

    final client = MockClient((request) async {
      if (request.method == "POST") {
        expect(
          request.url.path,
          "/api/v1/inspections/" + inspectionId + "/submit",
        );
        return http.Response(
          jsonEncode(<String, Object?>{
            "id": inspectionId,
            "status": "pending_review",
            "submitted_at": "2026-09-23T12:00:00Z",
            "reopened_for_recheck_at": reopenedAt,
          }),
          200,
        );
      }

      return http.Response(
        jsonEncode(<String, Object?>{
          "id": inspectionId,
          "status": status,
          "submitted_at":
              status == "pending_review" ? "2026-09-23T12:00:00Z" : null,
          "reopened_for_recheck_at": reopenedAt,
        }),
        200,
      );
    });
    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-submit",
      inspectionId: inspectionId,
      type: SyncOperationType.submitInspection,
      resourceId: inspectionId,
      payload: const <String, Object?>{
        "reopened_for_recheck_at": null,
      },
    );

    expect(
      (await adapter.execute(operation)).remoteResourceId,
      inspectionId,
    );
    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.applied,
    );

    status = "draft";
    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.notApplied,
    );

    reopenedAt = "2026-09-23T12:30:00Z";
    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.applied,
    );
  });

  test("recheck reopening reconciles by changed reopen timestamp", () async {
    const previous = "2026-09-23T11:00:00.000Z";
    var status = "draft";
    var reopenedAt = "2026-09-23T13:00:00.000Z";

    final client = MockClient((request) async {
      if (request.method == "POST") {
        expect(
          request.url.path,
          "/api/v1/inspections/" +
              inspectionId +
              "/reopen-for-recheck",
        );
      }
      return http.Response(
        jsonEncode(<String, Object?>{
          "id": inspectionId,
          "status": status,
          "submitted_at": status == "pending_review"
              ? "2026-09-23T12:00:00Z"
              : null,
          "reopened_for_recheck_at": reopenedAt,
        }),
        200,
      );
    });
    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-reopen",
      inspectionId: inspectionId,
      type: SyncOperationType.reopenForRecheck,
      resourceId: inspectionId,
      payload: const <String, Object?>{
        "previous_reopened_for_recheck_at": previous,
      },
    );

    expect(
      (await adapter.execute(operation)).remoteResourceId,
      inspectionId,
    );
    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.applied,
    );

    status = "pending_review";
    reopenedAt = previous;
    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.notApplied,
    );
  });

  test("Officer review execution verifies returned review identity", () async {
    const reviewId = "89898989-8989-4898-8898-898989898989";
    const resultId = "90909090-9090-4090-8090-909090909090";

    final client = MockClient((request) async {
      expect(request.method, "POST");
      expect(
        request.url.path,
        "/api/v1/inspections/" +
            inspectionId +
            "/rule-reviews/" +
            resultId,
      );
      final body = jsonDecode(request.body) as Map<String, dynamic>;
      expect(body["id"], reviewId);
      expect(body["decision"], "accepted");
      expect(body["note"], "Verified.");

      return http.Response(
        jsonEncode(<String, Object?>{
          "id": reviewId,
          "inspection_id": inspectionId,
          "rule_evaluation_result_id": resultId,
          "decision": "accepted",
          "corrected_value": null,
          "note": "Verified.",
        }),
        200,
      );
    });

    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-review",
      inspectionId: inspectionId,
      type: SyncOperationType.createOfficerReview,
      resourceId: reviewId,
      payload: const <String, Object?>{
        "id": reviewId,
        "rule_evaluation_result_id": resultId,
        "decision": "accepted",
        "note": "Verified.",
      },
    );

    final result = await adapter.execute(operation);
    expect(result.remoteResourceId, reviewId);
  });

  test("malformed success response is outcome-unknown, not accepted", () async {
    final client = MockClient((request) async {
      return http.Response("not-json", 201);
    });
    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-inspection-malformed",
      inspectionId: inspectionId,
      type: SyncOperationType.createInspection,
      resourceId: inspectionId,
      payload: const <String, Object?>{
        "id": inspectionId,
        "product_name": "Offline Product",
        "product_identifier": null,
      },
    );

    await expectLater(
      adapter.execute(operation),
      throwsA(
        isA<SyncRequestFailure>()
            .having(
              (error) => error.apiCode,
              "apiCode",
              "response_unverifiable",
            )
            .having(
              (error) => error.outcomeUnknown,
              "outcomeUnknown",
              isTrue,
            ),
      ),
    );
  });

  test("preprocessing composite executes and reconciles exact output IDs", () async {
    const derivativeId = "57575757-5757-4575-8575-575757575757";
    const qualityId = "58585858-5858-4585-8585-585858585858";

    final client = MockClient((request) async {
      if (request.method == "POST") {
        expect(
          request.url.path,
          "/api/v1/inspections/" +
              inspectionId +
              "/captures/" +
              captureId +
              "/process",
        );
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body["derivative_id"], derivativeId);
        expect(body["quality_assessment_id"], qualityId);
      } else {
        expect(
          request.url.path,
          "/api/v1/inspections/" +
              inspectionId +
              "/captures/" +
              captureId +
              "/process-runs/" +
              qualityId,
        );
      }

      return http.Response(
        jsonEncode(<String, Object?>{
          "derivative": <String, Object?>{
            "id": derivativeId,
            "capture_id": captureId,
          },
          "quality": <String, Object?>{
            "id": qualityId,
            "capture_id": captureId,
            "derivative_id": derivativeId,
          },
        }),
        200,
      );
    });

    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-process",
      inspectionId: inspectionId,
      type: SyncOperationType.processCapture,
      resourceId: qualityId,
      payload: const <String, Object?>{
        "capture_id": captureId,
        "derivative_id": derivativeId,
        "quality_assessment_id": qualityId,
      },
    );

    expect(
      (await adapter.execute(operation)).remoteResourceId,
      qualityId,
    );
    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.applied,
    );
  });

  test("geometry composite executes and reconciles corrected derivative", () async {
    const geometryId = "67676767-6767-4676-8676-676767676767";
    const correctedId = "68686868-6868-4686-8686-686868686868";

    final client = MockClient((request) async {
      if (request.method == "POST") {
        expect(
          request.url.path,
          "/api/v1/inspections/" +
              inspectionId +
              "/captures/" +
              captureId +
              "/geometry/analyze",
        );
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body["geometry_assessment_id"], geometryId);
        expect(body["corrected_derivative_id"], correctedId);
      } else {
        expect(
          request.url.path,
          "/api/v1/inspections/" +
              inspectionId +
              "/captures/" +
              captureId +
              "/geometry/runs/" +
              geometryId,
        );
      }

      return http.Response(
        jsonEncode(<String, Object?>{
          "geometry": <String, Object?>{
            "id": geometryId,
            "capture_id": captureId,
            "corrected_derivative_id": correctedId,
          },
          "corrected_derivative": <String, Object?>{
            "id": correctedId,
            "capture_id": captureId,
          },
        }),
        200,
      );
    });

    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-geometry",
      inspectionId: inspectionId,
      type: SyncOperationType.analyzeGeometry,
      resourceId: geometryId,
      payload: const <String, Object?>{
        "capture_id": captureId,
        "geometry_assessment_id": geometryId,
        "corrected_derivative_id": correctedId,
      },
    );

    expect(
      (await adapter.execute(operation)).remoteResourceId,
      geometryId,
    );
    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.applied,
    );
  });

  test("geometry no-correction response leaves candidate derivative unused", () async {
    const geometryId = "69696969-6969-4696-8696-696969696969";
    const correctedCandidateId =
        "70707070-7070-4707-8707-707070707070";

    final client = MockClient((request) async {
      return http.Response(
        jsonEncode(<String, Object?>{
          "geometry": <String, Object?>{
            "id": geometryId,
            "capture_id": captureId,
            "corrected_derivative_id": null,
          },
          "corrected_derivative": null,
        }),
        200,
      );
    });
    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-geometry-no-correction",
      inspectionId: inspectionId,
      type: SyncOperationType.analyzeGeometry,
      resourceId: geometryId,
      payload: const <String, Object?>{
        "capture_id": captureId,
        "geometry_assessment_id": geometryId,
        "corrected_derivative_id": correctedCandidateId,
      },
    );

    expect(
      (await adapter.execute(operation)).remoteResourceId,
      geometryId,
    );
  });

  test("OCR stable run executes and reconciles by exact run ID", () async {
    const ocrRunId = "41414141-4141-4414-8414-414141414141";
    var postCount = 0;

    final client = MockClient((request) async {
      if (request.method == "POST") {
        postCount += 1;
        expect(
          request.url.path,
          "/api/v1/inspections/" +
              inspectionId +
              "/captures/" +
              captureId +
              "/ocr/run",
        );
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body["id"], ocrRunId);
      } else {
        expect(
          request.url.path,
          "/api/v1/inspections/" +
              inspectionId +
              "/captures/" +
              captureId +
              "/ocr/runs/" +
              ocrRunId,
        );
      }

      return http.Response(
        jsonEncode(<String, Object?>{
          "run": <String, Object?>{
            "id": ocrRunId,
            "capture_id": captureId,
          },
          "blocks": <Object?>[],
        }),
        200,
      );
    });

    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-ocr",
      inspectionId: inspectionId,
      type: SyncOperationType.runOcr,
      resourceId: ocrRunId,
      payload: const <String, Object?>{
        "id": ocrRunId,
        "capture_id": captureId,
      },
    );

    expect(
      (await adapter.execute(operation)).remoteResourceId,
      ocrRunId,
    );
    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.applied,
    );
    expect(postCount, 1);
  });

  test("declaration extraction stable run uses exact reconciliation endpoint", () async {
    const extractionRunId = "42424242-4242-4424-8424-424242424242";
    final client = MockClient((request) async {
      if (request.method == "POST") {
        expect(
          request.url.path,
          "/api/v1/inspections/" +
              inspectionId +
              "/declarations/extract",
        );
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body["id"], extractionRunId);
      } else {
        expect(
          request.url.path,
          "/api/v1/inspections/" +
              inspectionId +
              "/declarations/runs/" +
              extractionRunId,
        );
      }

      return http.Response(
        jsonEncode(<String, Object?>{
          "run": <String, Object?>{
            "id": extractionRunId,
            "inspection_id": inspectionId,
          },
          "observations": <Object?>[],
          "summaries": <Object?>[],
        }),
        200,
      );
    });

    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-extraction",
      inspectionId: inspectionId,
      type: SyncOperationType.extractDeclarations,
      resourceId: extractionRunId,
      payload: const <String, Object?>{"id": extractionRunId},
    );

    expect(
      (await adapter.execute(operation)).remoteResourceId,
      extractionRunId,
    );
    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.applied,
    );
  });

  test("rule evaluation stable run verifies and reconciles context", () async {
    const evaluationRunId = "43434343-4343-4434-8434-434343434343";
    const context = <String, Object?>{
      "intended_for_retail_sale": true,
      "industrial_or_institutional_consumer": false,
      "package_exceeds_25kg_or_25l": false,
    };

    final client = MockClient((request) async {
      if (request.method == "POST") {
        expect(
          request.url.path,
          "/api/v1/inspections/" +
              inspectionId +
              "/rule-evaluations/evaluate",
        );
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body["id"], evaluationRunId);
        expect(body["context"], context);
      } else {
        expect(
          request.url.path,
          "/api/v1/inspections/" +
              inspectionId +
              "/rule-evaluations/runs/" +
              evaluationRunId,
        );
      }

      return http.Response(
        jsonEncode(<String, Object?>{
          "run": <String, Object?>{
            "id": evaluationRunId,
            "inspection_id": inspectionId,
            "context_snapshot": context,
          },
          "results": <Object?>[],
        }),
        200,
      );
    });

    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-evaluation",
      inspectionId: inspectionId,
      type: SyncOperationType.evaluateRules,
      resourceId: evaluationRunId,
      payload: const <String, Object?>{
        "id": evaluationRunId,
        "context": context,
      },
    );

    expect(
      (await adapter.execute(operation)).remoteResourceId,
      evaluationRunId,
    );
    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.applied,
    );
  });

  test("capture integrity mismatch fails before network request", () async {
    final tempDirectory = await Directory.systemTemp.createTemp(
      "codeflux_api_integrity_",
    );
    addTearDown(() async {
      if (await tempDirectory.exists()) {
        await tempDirectory.delete(recursive: true);
      }
    });

    final file = File(p.join(tempDirectory.path, "front.jpg"));
    await file.writeAsBytes(<int>[1, 2, 3]);

    var calls = 0;
    final client = MockClient((request) async {
      calls += 1;
      return http.Response("{}", 500);
    });
    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-capture",
      inspectionId: inspectionId,
      type: SyncOperationType.uploadCapture,
      resourceId: captureId,
      payload: <String, Object?>{
        "capture_id": captureId,
        "view_type": "front",
        "local_path": file.path,
        "sha256":
            "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        "size_bytes": 3,
      },
    );

    await expectLater(
      adapter.execute(operation),
      throwsA(
        isA<SyncRequestFailure>().having(
          (error) => error.apiCode,
          "apiCode",
          "local_evidence_integrity_failed",
        ),
      ),
    );
    expect(calls, 0);
  });

  test("capture reconciliation verifies checksum, size and view", () async {
    final digest =
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    final client = MockClient((request) async {
      expect(request.method, "GET");
      return http.Response(
        jsonEncode(<Object?>[
          <String, Object?>{
            "id": captureId,
            "inspection_id": inspectionId,
            "sha256": digest,
            "size_bytes": 321,
            "view_type": "detail",
          },
        ]),
        200,
      );
    });
    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-capture",
      inspectionId: inspectionId,
      type: SyncOperationType.uploadCapture,
      resourceId: captureId,
      payload: <String, Object?>{
        "capture_id": captureId,
        "view_type": "detail",
        "local_path": "/unused/in/reconciliation.jpg",
        "sha256": digest,
        "size_bytes": 321,
      },
    );

    final reconciliation = await adapter.reconcile(operation);
    expect(reconciliation.status, ReconciliationStatus.applied);
  });

  test("inspection update execution and reconciliation preserve edited details", () async {
    var remoteName = "Correct Product";
    String? remoteIdentifier = "NEW-1";

    final client = MockClient((request) async {
      if (request.method == "PATCH") {
        expect(
          request.url.path,
          "/api/v1/inspections/" + inspectionId,
        );
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body["product_name"], "Correct Product");
        expect(body["product_identifier"], "NEW-1");
        return http.Response(
          jsonEncode(<String, Object?>{
            "id": inspectionId,
            "product_name": "Correct Product",
            "product_identifier": "NEW-1",
            "status": "draft",
          }),
          200,
        );
      }

      expect(request.method, "GET");
      return http.Response(
        jsonEncode(<String, Object?>{
          "id": inspectionId,
          "product_name": remoteName,
          "product_identifier": remoteIdentifier,
          "status": "draft",
        }),
        200,
      );
    });

    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-update-inspection",
      inspectionId: inspectionId,
      type: SyncOperationType.updateInspection,
      resourceId: inspectionId,
      payload: const <String, Object?>{
        "product_name": "Correct Product",
        "product_identifier": "NEW-1",
      },
    );

    expect(
      (await adapter.execute(operation)).remoteResourceId,
      inspectionId,
    );
    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.applied,
    );

    remoteName = "Old Product";
    remoteIdentifier = null;
    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.notApplied,
    );
  });

  test("inspection discard execution and reconciliation verify discarded state", () async {
    var remoteStatus = "discarded";
    final client = MockClient((request) async {
      if (request.method == "POST") {
        expect(
          request.url.path,
          "/api/v1/inspections/" + inspectionId + "/discard",
        );
        return http.Response(
          jsonEncode(<String, Object?>{
            "id": inspectionId,
            "status": "discarded",
          }),
          200,
        );
      }

      expect(request.method, "GET");
      return http.Response(
        jsonEncode(<String, Object?>{
          "id": inspectionId,
          "status": remoteStatus,
        }),
        200,
      );
    });

    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-discard-inspection",
      inspectionId: inspectionId,
      type: SyncOperationType.discardInspection,
      resourceId: inspectionId,
      payload: const <String, Object?>{},
    );

    expect(
      (await adapter.execute(operation)).remoteResourceId,
      inspectionId,
    );
    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.applied,
    );

    remoteStatus = "draft";
    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.notApplied,
    );
  });


  test("capture discard execution and reconciliation verify removal", () async {
    var discardedAt = "2026-09-24T11:00:00Z";
    final client = MockClient((request) async {
      expect(
        request.url.path,
        "/api/v1/inspections/" +
            inspectionId +
            "/captures/" +
            captureId +
            (request.method == "POST" ? "/discard" : ""),
      );

      if (request.method == "POST") {
        return http.Response(
          jsonEncode(<String, Object?>{
            "id": captureId,
            "inspection_id": inspectionId,
            "discarded_at": discardedAt,
          }),
          200,
        );
      }

      return http.Response(
        jsonEncode(<String, Object?>{
          "id": captureId,
          "inspection_id": inspectionId,
          "discarded_at": discardedAt.isEmpty ? null : discardedAt,
        }),
        200,
      );
    });

    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-discard-capture",
      inspectionId: inspectionId,
      type: SyncOperationType.discardCapture,
      resourceId: captureId,
      payload: const <String, Object?>{
        "capture_id": captureId,
      },
    );

    expect(
      (await adapter.execute(operation)).remoteResourceId,
      captureId,
    );
    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.applied,
    );

    discardedAt = "";
    expect(
      (await adapter.reconcile(operation)).status,
      ReconciliationStatus.notApplied,
    );
  });

  test("missing capture satisfies discard reconciliation goal", () async {
    final client = MockClient((request) async => http.Response("{}", 404));
    final adapter = CodefluxApiSyncAdapter(
      client: client,
      serverBaseUri: Uri.parse("https://example.test/"),
      accessTokenProvider: () async => "token",
    );
    final operation = SyncOperation.queued(
      id: "op-discard-missing-capture",
      inspectionId: inspectionId,
      type: SyncOperationType.discardCapture,
      resourceId: captureId,
      payload: const <String, Object?>{
        "capture_id": captureId,
      },
    );

    final result = await adapter.reconcile(operation);
    expect(result.status, ReconciliationStatus.applied);
    expect(result.remoteResourceId, captureId);
  });

}
