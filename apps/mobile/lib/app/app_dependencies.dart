import "dart:io";

import "package:http/http.dart" as http;
import "package:path/path.dart" as p;
import "package:path_provider/path_provider.dart";

import "../auth/codeflux_officer_auth_client.dart";
import "../auth/officer_session_store.dart";
import "../capture/evidence_acquisition_service.dart";
import "../capture/field_capture_coordinator.dart";
import "../capture/pending_capture_repository.dart";
import "../offline/persistence/local_draft_repository.dart";
import "../offline/persistence/offline_database.dart";
import "../offline/persistence/sync_queue_repository.dart";
import "../offline/storage/local_evidence_store.dart";
import "../offline/sync/codeflux_api_sync_adapter.dart";
import "../offline/sync/offline_sync_service.dart";
import "../offline/sync/sync_coordinator.dart";
import "../offline/workflow/field_inspection_workflow_service.dart";
import "officer_workspace_service.dart";

class AppDependencies {
  AppDependencies._({
    required this.httpClient,
    required this.database,
    required this.authClient,
    required this.workspace,
    required this.captureCoordinator,
  });

  final http.Client httpClient;
  final OfflineDatabase database;
  final CodefluxOfficerAuthClient authClient;
  final OfficerWorkspaceService workspace;
  final FieldCaptureCoordinator captureCoordinator;

  static Future<AppDependencies> create({
    required Uri serverBaseUri,
  }) async {
    final httpClient = http.Client();
    final database = await OfflineDatabase.openDefault();
    final drafts = LocalDraftRepository(database);
    final queue = SyncQueueRepository(database);
    final sessionStore = OfficerSessionStore(
      FlutterSecureKeyValueStore(),
    );

    final support = await getApplicationSupportDirectory();
    final evidenceRoot = Directory(
      p.join(support.path, "codeflux", "evidence"),
    );
    final evidenceStore = LocalEvidenceStore(evidenceRoot);

    final apiAdapter = CodefluxApiSyncAdapter(
      client: httpClient,
      serverBaseUri: serverBaseUri,
      accessTokenProvider: OfficerSessionTokenProvider(sessionStore),
    );
    final syncCoordinator = SyncCoordinator(
      queue: queue,
      executor: apiAdapter,
      reconciler: apiAdapter,
    );
    final syncService = OfflineSyncService(
      coordinator: syncCoordinator,
    );
    final workflow = FieldInspectionWorkflowService(
      drafts: drafts,
      queue: queue,
      evidenceStore: evidenceStore,
    );
    final workspace = OfficerWorkspaceService(
      sessionStore: sessionStore,
      drafts: drafts,
      queue: queue,
      workflow: workflow,
      syncService: syncService,
    );
    final authClient = CodefluxOfficerAuthClient(
      client: httpClient,
      serverBaseUri: serverBaseUri,
      sessionStore: sessionStore,
    );
    final captureCoordinator = FieldCaptureCoordinator(
      workspace: workspace,
      acquisition: ImagePickerEvidenceAcquisitionService(),
      pendingCaptures: PendingCaptureRepository(database),
    );

    return AppDependencies._(
      httpClient: httpClient,
      database: database,
      authClient: authClient,
      workspace: workspace,
      captureCoordinator: captureCoordinator,
    );
  }

  Future<void> dispose() async {
    httpClient.close();
    await database.close();
  }
}
