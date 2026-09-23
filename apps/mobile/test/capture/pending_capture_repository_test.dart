import "dart:io";

import "package:flutter_test/flutter_test.dart";
import "package:path/path.dart" as p;
import "package:sqflite_common_ffi/sqflite_ffi.dart";

import "package:codeflux_mobile/offline/persistence/local_draft_repository.dart";
import "package:codeflux_mobile/offline/persistence/offline_database.dart";
import "package:codeflux_mobile/capture/pending_capture_repository.dart";

void main() {
  setUpAll(sqfliteFfiInit);

  test("only one image acquisition may be pending", () async {
    final root = await Directory.systemTemp.createTemp("codeflux_pending_");
    final database = await OfflineDatabase.openAt(
      p.join(root.path, "offline.sqlite3"),
      factory: databaseFactoryFfi,
    );
    addTearDown(() async {
      await database.close();
      if (await root.exists()) {
        await root.delete(recursive: true);
      }
    });

    final drafts = LocalDraftRepository(database);
    await drafts.createInspection(
      id: "inspection-1",
      officerUserId: "officer-1",
      productName: "Package",
    );

    final repository = PendingCaptureRepository(database);
    final first = await repository.begin(
      inspectionId: "inspection-1",
      viewType: "front",
      source: "camera",
      now: DateTime.utc(2026, 9, 23, 12),
    );

    expect((await repository.current())!.id, first.id);

    await expectLater(
      repository.begin(
        inspectionId: "inspection-1",
        viewType: "back",
        source: "gallery",
      ),
      throwsA(isA<StateError>()),
    );

    await repository.complete(first.id);
    expect(await repository.current(), isNull);
  });
}
