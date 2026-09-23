import "package:uuid/uuid.dart";

import "../offline/persistence/offline_database.dart";

class PendingCaptureIntent {
  const PendingCaptureIntent({
    required this.id,
    required this.inspectionId,
    required this.viewType,
    required this.source,
    required this.createdAt,
  });

  final String id;
  final String inspectionId;
  final String viewType;
  final String source;
  final DateTime createdAt;
}

class PendingCaptureRepository {
  PendingCaptureRepository(
    this.offlineDatabase, {
    Uuid? uuid,
  }) : _uuid = uuid ?? Uuid();

  final OfflineDatabase offlineDatabase;
  final Uuid _uuid;

  Future<PendingCaptureIntent> begin({
    required String inspectionId,
    required String viewType,
    required String source,
    DateTime? now,
  }) async {
    final active = await current();
    if (active != null) {
      throw StateError(
        "Another image acquisition is already pending and must be resolved first.",
      );
    }

    final normalizedView = viewType.trim();
    final normalizedSource = source.trim();
    if (normalizedView.isEmpty || normalizedSource.isEmpty) {
      throw ArgumentError("View type and source must not be blank.");
    }

    final timestamp = (now ?? DateTime.now().toUtc()).toUtc();
    final intent = PendingCaptureIntent(
      id: _uuid.v4(),
      inspectionId: inspectionId,
      viewType: normalizedView,
      source: normalizedSource,
      createdAt: timestamp,
    );

    await offlineDatabase.database.insert(
      "pending_capture_intents",
      <String, Object?>{
        "id": intent.id,
        "inspection_id": intent.inspectionId,
        "view_type": intent.viewType,
        "source": intent.source,
        "created_at": intent.createdAt.toIso8601String(),
      },
    );
    return intent;
  }

  Future<PendingCaptureIntent?> current() async {
    final rows = await offlineDatabase.database.query(
      "pending_capture_intents",
      orderBy: "created_at DESC, id ASC",
    );
    if (rows.isEmpty) {
      return null;
    }
    if (rows.length != 1) {
      throw StateError(
        "Multiple pending image acquisitions exist; recovery is ambiguous.",
      );
    }
    return _fromRow(rows.single);
  }

  Future<void> complete(String id) async {
    final deleted = await offlineDatabase.database.delete(
      "pending_capture_intents",
      where: "id = ?",
      whereArgs: <Object?>[id],
    );
    if (deleted != 1) {
      throw StateError("Pending image acquisition does not exist.");
    }
  }

  Future<void> discard(String id) => complete(id);

  PendingCaptureIntent _fromRow(Map<String, Object?> row) {
    return PendingCaptureIntent(
      id: row["id"]! as String,
      inspectionId: row["inspection_id"]! as String,
      viewType: row["view_type"]! as String,
      source: row["source"]! as String,
      createdAt: DateTime.parse(row["created_at"]! as String).toUtc(),
    );
  }
}
