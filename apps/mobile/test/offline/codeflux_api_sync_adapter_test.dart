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
              "sha256": digest,
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
}
