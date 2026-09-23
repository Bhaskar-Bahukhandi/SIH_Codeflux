import "package:flutter_test/flutter_test.dart";

import "package:codeflux_mobile/offline/models/local_records.dart";
import "package:codeflux_mobile/offline/models/sync_operation.dart";
import "package:codeflux_mobile/offline/models/sync_state.dart";
import "package:codeflux_mobile/offline/sync/sync_operation_factory.dart";

void main() {
  test("factory creates canonical inspection and capture dependency payloads", () {
    final now = DateTime.utc(2026, 9, 23, 22);
    const inspectionId = "99999999-9999-4999-8999-999999999999";
    const evidenceId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
    const createOperationId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
    const captureOperationId = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";

    final factory = SyncOperationFactory();
    final inspection = LocalInspectionDraft(
      id: inspectionId,
      productName: "Canonical Product",
      productIdentifier: "SKU-1",
      syncState: SyncState.localOnly,
      createdAt: now,
      updatedAt: now,
    );
    final create = factory.createInspection(
      inspection,
      operationId: createOperationId,
      now: now,
    );

    expect(create.type, SyncOperationType.createInspection);
    expect(create.resourceId, inspectionId);
    expect(create.payload["id"], inspectionId);
    expect(create.payload["product_name"], "Canonical Product");
    expect(create.payload["product_identifier"], "SKU-1");

    final evidence = LocalEvidenceRecord(
      id: evidenceId,
      inspectionId: inspectionId,
      viewType: "front",
      localPath: "/local/front.jpg",
      sha256:
          "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
      sizeBytes: 123,
      syncState: SyncState.localOnly,
      createdAt: now,
      updatedAt: now,
    );
    final capture = factory.uploadCapture(
      evidence,
      createInspectionOperationId: createOperationId,
      operationId: captureOperationId,
      now: now,
    );

    expect(capture.type, SyncOperationType.uploadCapture);
    expect(capture.resourceId, evidenceId);
    expect(capture.dependencyIds, <String>[createOperationId]);
    expect(capture.payload["capture_id"], evidenceId);
    expect(capture.payload["local_path"], "/local/front.jpg");
    expect(capture.payload["size_bytes"], 123);
  });

  test("review factory trims optional note and preserves stable review ID", () {
    final factory = SyncOperationFactory();
    const reviewId = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";

    final review = factory.createOfficerReview(
      inspectionId: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
      reviewId: reviewId,
      ruleEvaluationResultId: "ffffffff-ffff-4fff-8fff-ffffffffffff",
      decision: "accepted",
      note: "  Verified evidence.  ",
      operationId: "12121212-1212-4212-8212-121212121212",
    );

    expect(review.type, SyncOperationType.createOfficerReview);
    expect(review.resourceId, reviewId);
    expect(review.payload["id"], reviewId);
    expect(review.payload["note"], "Verified evidence.");
  });
}
