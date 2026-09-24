import "dart:io";

import "package:path/path.dart" as p;
import "package:path_provider/path_provider.dart";
import "package:sqflite/sqflite.dart" show databaseFactory;
import "package:sqflite_common/sqlite_api.dart"
    show Database, DatabaseFactory, OpenDatabaseOptions;

class OfflineDatabase {
  OfflineDatabase._(this.database);

  static const int schemaVersion = 4;
  static const String databaseFileName = "codeflux_offline.sqlite3";

  final Database database;

  static Future<OfflineDatabase> openDefault() async {
    final supportDirectory = await getApplicationSupportDirectory();
    final databaseDirectory = Directory(
      p.join(supportDirectory.path, "codeflux"),
    );
    await databaseDirectory.create(recursive: true);
    return openAt(p.join(databaseDirectory.path, databaseFileName));
  }

  static Future<OfflineDatabase> openAt(
    String path, {
    DatabaseFactory? factory,
  }) async {
    final selectedFactory = factory ?? databaseFactory;
    final database = await selectedFactory.openDatabase(
      path,
      options: OpenDatabaseOptions(
        version: schemaVersion,
        onConfigure: (db) async {
          await db.execute("PRAGMA foreign_keys = ON");
        },
        onCreate: (db, version) async {
          await _createSchema(db);
        },
        onUpgrade: (db, oldVersion, newVersion) async {
          await _upgradeSchema(db, oldVersion, newVersion);
        },
      ),
    );
    return OfflineDatabase._(database);
  }

  static Future<void> _createSchema(Database db) async {
    await db.execute("""
      CREATE TABLE local_inspections (
        id TEXT PRIMARY KEY,
        product_name TEXT NOT NULL,
        product_identifier TEXT,
        officer_user_id TEXT,
        sync_state TEXT NOT NULL,
        remote_id TEXT,
        last_error_kind TEXT,
        last_error_code TEXT,
        last_error_message TEXT,
        discarded_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      )
    """);

    await db.execute("""
      CREATE TABLE local_evidence (
        id TEXT PRIMARY KEY,
        inspection_id TEXT NOT NULL,
        view_type TEXT NOT NULL,
        local_path TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
        sync_state TEXT NOT NULL,
        remote_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (inspection_id)
          REFERENCES local_inspections(id)
          ON DELETE RESTRICT
      )
    """);

    await db.execute("""
      CREATE TABLE sync_operations (
        id TEXT PRIMARY KEY,
        inspection_id TEXT NOT NULL,
        operation_type TEXT NOT NULL,
        resource_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        payload_sha256 TEXT NOT NULL,
        dependency_ids_json TEXT NOT NULL,
        state TEXT NOT NULL,
        attempt_count INTEGER NOT NULL DEFAULT 0
          CHECK (attempt_count >= 0),
        next_attempt_at TEXT,
        last_attempt_at TEXT,
        last_error_kind TEXT,
        last_error_code TEXT,
        last_error_message TEXT,
        remote_resource_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (inspection_id)
          REFERENCES local_inspections(id)
          ON DELETE RESTRICT
      )
    """);

    await db.execute(
      "CREATE INDEX ix_local_evidence_inspection "
      "ON local_evidence(inspection_id, created_at)",
    );
    await db.execute(
      "CREATE INDEX ix_sync_operations_ready "
      "ON sync_operations(state, next_attempt_at, created_at)",
    );
    await db.execute(
      "CREATE INDEX ix_sync_operations_inspection "
      "ON sync_operations(inspection_id, created_at)",
    );

    await db.execute("""
      CREATE TABLE pending_capture_intents (
        id TEXT PRIMARY KEY,
        inspection_id TEXT NOT NULL,
        view_type TEXT NOT NULL,
        source TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (inspection_id)
          REFERENCES local_inspections(id)
          ON DELETE RESTRICT
      )
    """);
    await db.execute(
      "CREATE INDEX ix_pending_capture_intents_created "
      "ON pending_capture_intents(created_at DESC)",
    );
  }

  static Future<void> _upgradeSchema(
    Database db,
    int oldVersion,
    int newVersion,
  ) async {
    if (oldVersion < 2 && newVersion >= 2) {
      await db.execute(
        "ALTER TABLE local_inspections "
        "ADD COLUMN officer_user_id TEXT",
      );
    }
    if (oldVersion < 3 && newVersion >= 3) {
      await db.execute("""
        CREATE TABLE pending_capture_intents (
          id TEXT PRIMARY KEY,
          inspection_id TEXT NOT NULL,
          view_type TEXT NOT NULL,
          source TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY (inspection_id)
            REFERENCES local_inspections(id)
            ON DELETE RESTRICT
        )
      """);
      await db.execute(
        "CREATE INDEX ix_pending_capture_intents_created "
        "ON pending_capture_intents(created_at DESC)",
      );
    }
    if (oldVersion < 4 && newVersion >= 4) {
      await db.execute(
        "ALTER TABLE local_inspections "
        "ADD COLUMN discarded_at TEXT",
      );
    }
  }

  Future<void> close() => database.close();
}
