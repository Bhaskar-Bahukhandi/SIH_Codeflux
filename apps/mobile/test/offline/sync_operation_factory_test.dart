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

  test("preprocessing factory preserves paired stable output IDs", () {
    final factory = SyncOperationFactory();
    const inspectionId = "51515151-5151-4515-8515-515151515151";
    const captureId = "52525252-5252-4525-8525-525252525252";
    const derivativeId = "53535353-5353-4535-8535-535353535353";
    const qualityId = "54545454-5454-4545-8545-545454545454";
    const uploadDependency = "55555555-aaaa-4555-8555-555555555555";
    const operationId = "56565656-5656-4565-8565-565656565656";

    final processing = factory.processCapture(
      inspectionId: inspectionId,
      captureId: captureId,
      derivativeId: derivativeId,
      qualityAssessmentId: qualityId,
      dependencyIds: const <String>[uploadDependency],
      operationId: operationId,
    );

    expect(processing.type, SyncOperationType.processCapture);
    expect(processing.resourceId, qualityId);
    expect(processing.payload["capture_id"], captureId);
    expect(processing.payload["derivative_id"], derivativeId);
    expect(processing.payload["quality_assessment_id"], qualityId);
    expect(processing.dependencyIds, const <String>[uploadDependency]);
  });

  test("geometry factory preserves assessment and corrected candidate IDs", () {
    final factory = SyncOperationFactory();
    const inspectionId = "61616161-6161-4616-8616-616161616161";
    const captureId = "62626262-6262-4626-8626-626262626262";
    const geometryId = "63636363-6363-4636-8636-636363636363";
    const correctedId = "64646464-6464-4646-8646-646464646464";
    const processDependency = "65656565-6565-4656-8656-656565656565";

    final geometry = factory.analyzeGeometry(
      inspectionId: inspectionId,
      captureId: captureId,
      geometryAssessmentId: geometryId,
      correctedDerivativeId: correctedId,
      dependencyIds: const <String>[processDependency],
      operationId: "66666666-bbbb-4666-8666-666666666666",
    );

    expect(geometry.type, SyncOperationType.analyzeGeometry);
    expect(geometry.resourceId, geometryId);
    expect(geometry.payload["capture_id"], captureId);
    expect(geometry.payload["geometry_assessment_id"], geometryId);
    expect(geometry.payload["corrected_derivative_id"], correctedId);
    expect(geometry.dependencyIds, const <String>[processDependency]);
  });

  test("factory preserves stable run IDs and explicit pipeline dependencies", () {
    final factory = SyncOperationFactory();
    const inspectionId = "31313131-3131-4313-8313-313131313131";
    const captureId = "32323232-3232-4323-8323-323232323232";
    const ocrRunId = "33333333-3333-4333-8333-333333333333";
    const extractionRunId = "34343434-3434-4343-8343-343434343434";
    const evaluationRunId = "35353535-3535-4353-8353-353535353535";
    const captureDependency = "36363636-3636-4363-8363-363636363636";
    const ocrOperationId = "37373737-3737-4373-8373-373737373737";
    const extractionOperationId = "38383838-3838-4383-8383-383838383838";
    const evaluationOperationId = "39393939-3939-4393-8393-393939393939";

    final ocr = factory.runOcr(
      inspectionId: inspectionId,
      captureId: captureId,
      ocrRunId: ocrRunId,
      dependencyIds: const <String>[captureDependency],
      operationId: ocrOperationId,
    );
    expect(ocr.type, SyncOperationType.runOcr);
    expect(ocr.resourceId, ocrRunId);
    expect(ocr.payload["id"], ocrRunId);
    expect(ocr.payload["capture_id"], captureId);
    expect(ocr.dependencyIds, const <String>[captureDependency]);

    final extraction = factory.extractDeclarations(
      inspectionId: inspectionId,
      extractionRunId: extractionRunId,
      dependencyIds: const <String>[ocrOperationId],
      operationId: extractionOperationId,
    );
    expect(extraction.type, SyncOperationType.extractDeclarations);
    expect(extraction.resourceId, extractionRunId);
    expect(extraction.payload["id"], extractionRunId);
    expect(extraction.dependencyIds, const <String>[ocrOperationId]);

    final evaluation = factory.evaluateRules(
      inspectionId: inspectionId,
      evaluationRunId: evaluationRunId,
      context: const <String, Object?>{
        "intended_for_retail_sale": true,
        "industrial_or_institutional_consumer": false,
        "package_exceeds_25kg_or_25l": false,
      },
      dependencyIds: const <String>[extractionOperationId],
      operationId: evaluationOperationId,
    );
    expect(evaluation.type, SyncOperationType.evaluateRules);
    expect(evaluation.resourceId, evaluationRunId);
    expect(evaluation.payload["id"], evaluationRunId);
    expect(
      evaluation.payload["context"],
      const <String, Object?>{
        "intended_for_retail_sale": true,
        "industrial_or_institutional_consumer": false,
        "package_exceeds_25kg_or_25l": false,
      },
    );
    expect(
      evaluation.dependencyIds,
      const <String>[extractionOperationId],
    );
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
