import "dart:convert";
import "dart:io";
import "dart:typed_data";

import "package:flutter_test/flutter_test.dart";
import "package:http/http.dart" as http;
import "package:path/path.dart" as p;
import "package:sqflite_common_ffi/sqflite_ffi.dart";

import "package:codeflux_mobile/auth/codeflux_officer_auth_client.dart";
import "package:codeflux_mobile/auth/officer_session_store.dart";
import "package:codeflux_mobile/offline/models/sync_state.dart";
import "package:codeflux_mobile/offline/persistence/local_draft_repository.dart";
import "package:codeflux_mobile/offline/persistence/offline_database.dart";
import "package:codeflux_mobile/offline/persistence/sync_queue_repository.dart";
import "package:codeflux_mobile/offline/storage/local_evidence_store.dart";
import "package:codeflux_mobile/offline/sync/codeflux_api_sync_adapter.dart";
import "package:codeflux_mobile/offline/sync/offline_sync_service.dart";
import "package:codeflux_mobile/offline/sync/sync_coordinator.dart";
import "package:codeflux_mobile/offline/sync/sync_operation_factory.dart";

class MemorySecureStore implements SecureKeyValueStore {
  final Map<String, String> values = <String, String>{};

  @override
  Future<void> delete(String key) async {
    values.remove(key);
  }

  @override
  Future<String?> read(String key) async => values[key];

  @override
  Future<void> write(String key, String value) async {
    values[key] = value;
  }
}

String requiredEnvironment(String name) {
  final value = Platform.environment[name]?.trim();
  if (value == null || value.isEmpty) {
    throw StateError("Missing required integration environment variable: $name");
  }
  return value;
}

Map<String, dynamic> decodeObject(http.Response response) {
  expect(
    response.statusCode,
    inInclusiveRange(200, 299),
    reason: response.body,
  );
  final decoded = jsonDecode(response.body);
  expect(decoded, isA<Map>());
  return <String, dynamic>{
    for (final entry in (decoded as Map).entries)
      entry.key.toString(): entry.value,
  };
}

void main() {
  setUpAll(() {
    sqfliteFfiInit();
  });

  final liveIntegrationEnabled =
      Platform.environment["CODEFLUX_INTEGRATION_API_BASE"]?.trim().isNotEmpty ==
      true;

  test(
    "online auth then offline restart syncs through live FastAPI without duplicates",
    () async {
      final apiBase = Uri.parse(
        requiredEnvironment("CODEFLUX_INTEGRATION_API_BASE"),
      );
      final email = requiredEnvironment(
        "CODEFLUX_INTEGRATION_OFFICER_EMAIL",
      );
      final password = requiredEnvironment(
        "CODEFLUX_INTEGRATION_OFFICER_PASSWORD",
      );
      final fixturePath = requiredEnvironment("CODEFLUX_INTEGRATION_IMAGE");

      final sourceFixture = File(fixturePath);
      expect(await sourceFixture.exists(), isTrue);
      final fixtureBytes = await sourceFixture.readAsBytes();
      expect(fixtureBytes, isNotEmpty);

      const inspectionId = "91000000-0000-4900-8900-000000000001";
      const captureId = "91000000-0000-4900-8900-000000000002";

      const createOperationId = "92000000-0000-4900-8900-000000000001";
      const uploadOperationId = "92000000-0000-4900-8900-000000000002";
      const processOperationId = "92000000-0000-4900-8900-000000000003";
      const geometryOperationId = "92000000-0000-4900-8900-000000000004";
      const ocrOperationId = "92000000-0000-4900-8900-000000000005";
      const extractionOperationId = "92000000-0000-4900-8900-000000000006";
      const evaluationOperationId = "92000000-0000-4900-8900-000000000007";
      const submitOperationId = "92000000-0000-4900-8900-000000000008";

      const derivativeId = "93000000-0000-4900-8900-000000000001";
      const qualityId = "93000000-0000-4900-8900-000000000002";
      const geometryId = "93000000-0000-4900-8900-000000000003";
      const correctedCandidateId = "93000000-0000-4900-8900-000000000004";
      const ocrRunId = "93000000-0000-4900-8900-000000000005";
      const extractionRunId = "93000000-0000-4900-8900-000000000006";
      const evaluationRunId = "93000000-0000-4900-8900-000000000007";

      final root = await Directory.systemTemp.createTemp(
        "codeflux_live_fastapi_",
      );
      final databasePath = p.join(root.path, "offline.sqlite3");
      final evidenceStore = LocalEvidenceStore(
        Directory(p.join(root.path, "evidence")),
      );
      final clients = <http.Client>[];

      var database = await OfflineDatabase.openAt(
        databasePath,
        factory: databaseFactoryFfi,
      );
      addTearDown(() async {
        for (final client in clients) {
          client.close();
        }
        try {
          await database.close();
        } catch (_) {}
        if (await root.exists()) {
          await root.delete(recursive: true);
        }
      });

      // Start online: authenticate through the real FastAPI auth endpoints.
      final secureStore = MemorySecureStore();
      var sessionStore = OfficerSessionStore(secureStore);
      final authHttp = http.Client();
      clients.add(authHttp);
      final auth = CodefluxOfficerAuthClient(
        client: authHttp,
        serverBaseUri: apiBase,
        sessionStore: sessionStore,
      );
      final session = await auth.login(email: email, password: password);
      expect(session.role, "officer");

      var drafts = LocalDraftRepository(database);
      var queue = SyncQueueRepository(database);
      final factory = SyncOperationFactory();
      final offlineStart = DateTime.utc(2026, 9, 24, 6);

      // Connectivity is now considered unavailable: build the complete local
      // graph without making another HTTP request.
      final draft = await drafts.createInspection(
        id: inspectionId,
        officerUserId: session.userId,
        productName: "Live Integration Pack",
        productIdentifier: "LIVE-001",
        now: offlineStart,
      );

      final stored = await evidenceStore.persistBytes(
        inspectionId: inspectionId,
        evidenceId: captureId,
        bytes: Uint8List.fromList(fixtureBytes),
        originalFilename: "integration.jpg",
      );
      final evidence = await drafts.registerEvidence(
        id: captureId,
        inspectionId: inspectionId,
        viewType: "front",
        localPath: stored.path,
        sha256: stored.sha256,
        sizeBytes: stored.sizeBytes,
        now: offlineStart.add(const Duration(seconds: 1)),
      );

      final createOperation = factory.createInspection(
        draft,
        operationId: createOperationId,
        now: offlineStart.add(const Duration(seconds: 2)),
      );
      final uploadOperation = factory.uploadCapture(
        evidence,
        createInspectionOperationId: createOperationId,
        operationId: uploadOperationId,
        now: offlineStart.add(const Duration(seconds: 3)),
      );
      final processOperation = factory.processCapture(
        inspectionId: inspectionId,
        captureId: captureId,
        derivativeId: derivativeId,
        qualityAssessmentId: qualityId,
        dependencyIds: const <String>[uploadOperationId],
        operationId: processOperationId,
        now: offlineStart.add(const Duration(seconds: 4)),
      );
      final geometryOperation = factory.analyzeGeometry(
        inspectionId: inspectionId,
        captureId: captureId,
        geometryAssessmentId: geometryId,
        correctedDerivativeId: correctedCandidateId,
        dependencyIds: const <String>[processOperationId],
        operationId: geometryOperationId,
        now: offlineStart.add(const Duration(seconds: 5)),
      );
      final ocrOperation = factory.runOcr(
        inspectionId: inspectionId,
        captureId: captureId,
        ocrRunId: ocrRunId,
        dependencyIds: const <String>[geometryOperationId],
        operationId: ocrOperationId,
        now: offlineStart.add(const Duration(seconds: 6)),
      );
      final extractionOperation = factory.extractDeclarations(
        inspectionId: inspectionId,
        extractionRunId: extractionRunId,
        dependencyIds: const <String>[ocrOperationId],
        operationId: extractionOperationId,
        now: offlineStart.add(const Duration(seconds: 7)),
      );
      final evaluationOperation = factory.evaluateRules(
        inspectionId: inspectionId,
        evaluationRunId: evaluationRunId,
        context: const <String, Object?>{
          "intended_for_retail_sale": true,
          "industrial_or_institutional_consumer": false,
          "package_exceeds_25kg_or_25l": false,
        },
        dependencyIds: const <String>[extractionOperationId],
        operationId: evaluationOperationId,
        now: offlineStart.add(const Duration(seconds: 8)),
      );
      final submitOperation = factory.submitInspection(
        inspectionId: inspectionId,
        dependencyIds: const <String>[evaluationOperationId],
        operationId: submitOperationId,
        now: offlineStart.add(const Duration(seconds: 9)),
      );

      for (final operation in [
        createOperation,
        uploadOperation,
        processOperation,
        geometryOperation,
        ocrOperation,
        extractionOperation,
        evaluationOperation,
        submitOperation,
      ]) {
        await queue.enqueue(operation);
      }

      expect((await queue.listAll()).length, 8);
      expect(await evidenceStore.verify(stored), isTrue);

      // Simulate app/process restart before connectivity returns.
      await database.close();
      database = await OfflineDatabase.openAt(
        databasePath,
        factory: databaseFactoryFfi,
      );
      drafts = LocalDraftRepository(database);
      queue = SyncQueueRepository(database);
      sessionStore = OfficerSessionStore(secureStore);

      expect((await queue.listAll()).length, 8);
      expect(await evidenceStore.verify(stored), isTrue);
      final restoredSession = await sessionStore.read();
      expect(restoredSession, isNotNull);
      expect(restoredSession!.userId, session.userId);

      // Reconnect: the real mobile adapter now talks to the live FastAPI app.
      final syncHttp = http.Client();
      clients.add(syncHttp);
      final adapter = CodefluxApiSyncAdapter(
        client: syncHttp,
        serverBaseUri: apiBase,
        accessTokenProvider: OfficerSessionTokenProvider(sessionStore),
        requestTimeout: const Duration(seconds: 90),
      );
      final sync = OfflineSyncService(
        coordinator: SyncCoordinator(
          queue: queue,
          executor: adapter,
          reconciler: adapter,
        ),
      );

      final summary = await sync.recoverAndDrain(
        now: DateTime.utc(2026, 9, 24, 7),
      );
      expect(summary.recoveredInterrupted, 0);
      expect(summary.processed, 8);
      expect(summary.synced, 8);
      expect(summary.retryScheduled, 0);
      expect(summary.blocked, 0);
      expect(summary.conflicts, 0);
      expect(summary.reconciliationRequired, 0);
      expect(summary.limitReached, isFalse);

      final persistedOperations = await queue.listAll();
      expect(persistedOperations.length, 8);
      expect(
        persistedOperations.every(
          (operation) => operation.state == SyncState.synced,
        ),
        isTrue,
      );
      expect(
        (await drafts.getInspection(inspectionId))!.syncState,
        SyncState.synced,
      );
      expect(await evidenceStore.verify(stored), isTrue);

      // Replay the same stable resources directly against the real API.
      // Exact replay must return the existing resources rather than duplicate.
      expect(
        (await adapter.execute(createOperation)).remoteResourceId,
        inspectionId,
      );
      expect(
        (await adapter.execute(uploadOperation)).remoteResourceId,
        captureId,
      );

      final verifyHttp = http.Client();
      clients.add(verifyHttp);
      final headers = <String, String>{
        "Authorization": "Bearer ${session.accessToken}",
        "Accept": "application/json",
      };

      final inspectionResponse = await verifyHttp.get(
        apiBase.resolve("api/v1/inspections/$inspectionId"),
        headers: headers,
      );
      final remoteInspection = decodeObject(inspectionResponse);
      expect(remoteInspection["id"], inspectionId);
      expect(remoteInspection["status"], "pending_review");
      expect(remoteInspection["product_name"], "Live Integration Pack");

      final capturesResponse = await verifyHttp.get(
        apiBase.resolve("api/v1/inspections/$inspectionId/captures"),
        headers: headers,
      );
      expect(capturesResponse.statusCode, 200, reason: capturesResponse.body);
      final captures = jsonDecode(capturesResponse.body);
      expect(captures, isA<List>());
      expect((captures as List).length, 1);
      expect((captures.single as Map)["id"], captureId);
      expect((captures.single as Map)["sha256"], stored.sha256);

      final declarationsResponse = await verifyHttp.get(
        apiBase.resolve(
          "api/v1/inspections/$inspectionId/declarations/latest",
        ),
        headers: headers,
      );
      final declarations = decodeObject(declarationsResponse);
      expect((declarations["run"] as Map)["id"], extractionRunId);

      final evaluationResponse = await verifyHttp.get(
        apiBase.resolve(
          "api/v1/inspections/$inspectionId/rule-evaluations/latest",
        ),
        headers: headers,
      );
      final evaluation = decodeObject(evaluationResponse);
      expect((evaluation["run"] as Map)["id"], evaluationRunId);

      // A second queue drain must be a no-op after successful sync.
      final secondDrain = await sync.drain(
        now: DateTime.utc(2026, 9, 24, 7, 1),
      );
      expect(secondDrain.processed, 0);

      // Restart once more and prove durable queue/evidence state remains.
      await database.close();
      database = await OfflineDatabase.openAt(
        databasePath,
        factory: databaseFactoryFfi,
      );
      queue = SyncQueueRepository(database);
      expect(
        (await queue.listAll()).every(
          (operation) => operation.state == SyncState.synced,
        ),
        isTrue,
      );
      expect(await evidenceStore.verify(stored), isTrue);
    },
    timeout: const Timeout(Duration(minutes: 12)),
    skip: liveIntegrationEnabled
        ? false
        : "Requires the dedicated live FastAPI integration environment.",
  );
}
