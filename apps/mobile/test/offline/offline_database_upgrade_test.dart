import "dart:io";

import "package:flutter_test/flutter_test.dart";
import "package:path/path.dart" as p;
import "package:sqflite_common_ffi/sqflite_ffi.dart";

import "package:codeflux_mobile/offline/persistence/offline_database.dart";

void main() {
  setUpAll(sqfliteFfiInit);

  test("schema version 2 upgrades with pending capture table", () async {
    final root = await Directory.systemTemp.createTemp("codeflux_upgrade_");
    final path = p.join(root.path, "offline.sqlite3");

    final legacy = await databaseFactoryFfi.openDatabase(
      path,
      options: OpenDatabaseOptions(
        version: 2,
        onCreate: (db, version) async {
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
        },
      ),
    );
    await legacy.close();

    final upgraded = await OfflineDatabase.openAt(
      path,
      factory: databaseFactoryFfi,
    );
    addTearDown(() async {
      await upgraded.close();
      if (await root.exists()) {
        await root.delete(recursive: true);
      }
    });

    final tables = await upgraded.database.rawQuery(
      "SELECT name FROM sqlite_master WHERE type = 'table'",
    );
    final names = tables.map((row) => row["name"]).toSet();
    expect(names, contains("pending_capture_intents"));

    final evidenceColumns = await upgraded.database.rawQuery(
      "PRAGMA table_info(local_evidence)",
    );
    expect(
      evidenceColumns.map((row) => row["name"]).toSet(),
      contains("discarded_at"),
    );
  });
}
