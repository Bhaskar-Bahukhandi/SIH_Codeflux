import "../models/local_records.dart";
import "../models/sync_state.dart";
import "offline_database.dart";

class LocalDraftRepository {
  LocalDraftRepository(this.offlineDatabase);

  final OfflineDatabase offlineDatabase;

  Future<LocalInspectionDraft> createInspection({
    required String id,
    required String productName,
    String? productIdentifier,
    DateTime? now,
  }) async {
    final normalizedName = productName.trim();
    if (normalizedName.isEmpty) {
      throw ArgumentError.value(productName, "productName", "Must not be blank.");
    }
    final normalizedIdentifier = productIdentifier?.trim();
    final finalIdentifier =
        normalizedIdentifier == null || normalizedIdentifier.isEmpty
            ? null
            : normalizedIdentifier;
    final existing = await getInspection(id);
    if (existing != null) {
      if (existing.productName == normalizedName &&
          existing.productIdentifier == finalIdentifier) {
        return existing;
      }
      throw StateError(
        "Local inspection ID is already associated with different draft data.",
      );
    }

    final timestamp = (now ?? DateTime.now().toUtc()).toUtc();
    await offlineDatabase.database.insert(
      "local_inspections",
      <String, Object?>{
        "id": id,
        "product_name": normalizedName,
        "product_identifier": finalIdentifier,
        "sync_state": SyncState.localOnly.dbValue,
        "created_at": timestamp.toIso8601String(),
        "updated_at": timestamp.toIso8601String(),
      },
    );
    return (await getInspection(id))!;
  }

  Future<LocalInspectionDraft?> getInspection(String id) async {
    final rows = await offlineDatabase.database.query(
      "local_inspections",
      where: "id = ?",
      whereArgs: <Object?>[id],
      limit: 1,
    );
    if (rows.isEmpty) {
      return null;
    }
    return _inspectionFromRow(rows.single);
  }

  Future<LocalEvidenceRecord> registerEvidence({
    required String id,
    required String inspectionId,
    required String viewType,
    required String localPath,
    required String sha256,
    required int sizeBytes,
    DateTime? now,
  }) async {
    if (sizeBytes < 0) {
      throw ArgumentError.value(sizeBytes, "sizeBytes", "Must be non-negative.");
    }
    if (await getInspection(inspectionId) == null) {
      throw StateError("Local inspection does not exist.");
    }

    final existing = await getEvidence(id);
    if (existing != null) {
      if (existing.inspectionId == inspectionId &&
          existing.viewType == viewType &&
          existing.localPath == localPath &&
          existing.sha256 == sha256 &&
          existing.sizeBytes == sizeBytes) {
        return existing;
      }
      throw StateError(
        "Local evidence ID is already associated with different metadata.",
      );
    }

    final timestamp = (now ?? DateTime.now().toUtc()).toUtc();
    await offlineDatabase.database.insert(
      "local_evidence",
      <String, Object?>{
        "id": id,
        "inspection_id": inspectionId,
        "view_type": viewType,
        "local_path": localPath,
        "sha256": sha256,
        "size_bytes": sizeBytes,
        "sync_state": SyncState.localOnly.dbValue,
        "created_at": timestamp.toIso8601String(),
        "updated_at": timestamp.toIso8601String(),
      },
    );
    return (await getEvidence(id))!;
  }

  Future<LocalEvidenceRecord?> getEvidence(String id) async {
    final rows = await offlineDatabase.database.query(
      "local_evidence",
      where: "id = ?",
      whereArgs: <Object?>[id],
      limit: 1,
    );
    if (rows.isEmpty) {
      return null;
    }
    return _evidenceFromRow(rows.single);
  }

  Future<void> updateInspectionSyncState(
    String id,
    SyncState nextState, {
    String? remoteId,
    String? errorKind,
    String? errorCode,
    String? errorMessage,
    DateTime? now,
  }) async {
    final current = await getInspection(id);
    if (current == null) {
      throw StateError("Local inspection does not exist.");
    }
    SyncStateMachine.requireTransition(current.syncState, nextState);
    await offlineDatabase.database.update(
      "local_inspections",
      <String, Object?>{
        "sync_state": nextState.dbValue,
        "remote_id": remoteId ?? current.remoteId,
        "last_error_kind": errorKind,
        "last_error_code": errorCode,
        "last_error_message": errorMessage,
        "updated_at": (now ?? DateTime.now().toUtc())
            .toUtc()
            .toIso8601String(),
      },
      where: "id = ?",
      whereArgs: <Object?>[id],
    );
  }

  Future<void> updateEvidenceSyncState(
    String id,
    SyncState nextState, {
    String? remoteId,
    DateTime? now,
  }) async {
    final current = await getEvidence(id);
    if (current == null) {
      throw StateError("Local evidence does not exist.");
    }
    SyncStateMachine.requireTransition(current.syncState, nextState);
    await offlineDatabase.database.update(
      "local_evidence",
      <String, Object?>{
        "sync_state": nextState.dbValue,
        "remote_id": remoteId ?? current.remoteId,
        "updated_at": (now ?? DateTime.now().toUtc())
            .toUtc()
            .toIso8601String(),
      },
      where: "id = ?",
      whereArgs: <Object?>[id],
    );
  }

  LocalInspectionDraft _inspectionFromRow(Map<String, Object?> row) {
    return LocalInspectionDraft(
      id: row["id"]! as String,
      productName: row["product_name"]! as String,
      productIdentifier: row["product_identifier"] as String?,
      syncState: SyncState.fromDb(row["sync_state"]! as String),
      remoteId: row["remote_id"] as String?,
      lastErrorKind: row["last_error_kind"] as String?,
      lastErrorCode: row["last_error_code"] as String?,
      lastErrorMessage: row["last_error_message"] as String?,
      createdAt: DateTime.parse(row["created_at"]! as String).toUtc(),
      updatedAt: DateTime.parse(row["updated_at"]! as String).toUtc(),
    );
  }

  LocalEvidenceRecord _evidenceFromRow(Map<String, Object?> row) {
    return LocalEvidenceRecord(
      id: row["id"]! as String,
      inspectionId: row["inspection_id"]! as String,
      viewType: row["view_type"]! as String,
      localPath: row["local_path"]! as String,
      sha256: row["sha256"]! as String,
      sizeBytes: row["size_bytes"]! as int,
      syncState: SyncState.fromDb(row["sync_state"]! as String),
      remoteId: row["remote_id"] as String?,
      createdAt: DateTime.parse(row["created_at"]! as String).toUtc(),
      updatedAt: DateTime.parse(row["updated_at"]! as String).toUtc(),
    );
  }
}
