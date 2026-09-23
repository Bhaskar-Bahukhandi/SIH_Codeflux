import "dart:async";
import "dart:convert";
import "dart:io";

import "package:crypto/crypto.dart";
import "package:http/http.dart" as http;
import "package:path/path.dart" as p;

import "../models/sync_operation.dart";
import "sync_coordinator.dart";

typedef AccessTokenProvider = Future<String> Function();

class CodefluxApiSyncAdapter
    implements SyncOperationExecutor, SyncOperationReconciler {
  CodefluxApiSyncAdapter({
    required this.client,
    required this.serverBaseUri,
    required this.accessTokenProvider,
    this.requestTimeout = const Duration(seconds: 20),
  });

  final http.Client client;
  final Uri serverBaseUri;
  final AccessTokenProvider accessTokenProvider;
  final Duration requestTimeout;

  @override
  Future<SyncExecutionSuccess> execute(SyncOperation operation) {
    return switch (operation.type) {
      SyncOperationType.createInspection =>
        _executeCreateInspection(operation),
      SyncOperationType.uploadCapture =>
        _executeUploadCapture(operation),
      SyncOperationType.processCapture =>
        _executeProcessCapture(operation),
      SyncOperationType.analyzeGeometry =>
        _executeGeometry(operation),
      SyncOperationType.runOcr =>
        _executeOcr(operation),
      SyncOperationType.extractDeclarations =>
        _executeDeclarationExtraction(operation),
      SyncOperationType.evaluateRules =>
        _executeRuleEvaluation(operation),
      SyncOperationType.createOfficerReview =>
        _executeOfficerReview(operation),
      _ => throw UnsupportedError(
          "No API sync executor is implemented for " +
              operation.type.dbValue +
              ".",
        ),
    };
  }

  @override
  Future<ReconciliationResult> reconcile(SyncOperation operation) {
    return switch (operation.type) {
      SyncOperationType.createInspection =>
        _reconcileInspection(operation),
      SyncOperationType.uploadCapture =>
        _reconcileCapture(operation),
      SyncOperationType.processCapture =>
        _reconcileProcessCapture(operation),
      SyncOperationType.analyzeGeometry =>
        _reconcileGeometry(operation),
      SyncOperationType.runOcr =>
        _reconcileOcr(operation),
      SyncOperationType.extractDeclarations =>
        _reconcileDeclarationExtraction(operation),
      SyncOperationType.evaluateRules =>
        _reconcileRuleEvaluation(operation),
      SyncOperationType.createOfficerReview =>
        _reconcileOfficerReview(operation),
      _ => Future<ReconciliationResult>.value(
          const ReconciliationResult.unresolved(),
        ),
    };
  }

  Future<SyncExecutionSuccess> _executeCreateInspection(
    SyncOperation operation,
  ) async {
    final payload = operation.payload;
    final resourceId = _requiredString(payload, "id");
    if (resourceId != operation.resourceId) {
      throw StateError(
        "Inspection payload ID does not match the queued resource ID.",
      );
    }

    final body = <String, Object?>{
      "id": resourceId,
      "product_name": _requiredString(payload, "product_name"),
      "product_identifier": payload["product_identifier"],
    };
    final request = http.Request(
      "POST",
      _endpoint("api/v1/inspections"),
    )
      ..headers.addAll(await _headers(json: true))
      ..body = jsonEncode(body);

    final response = await _send(request);
    _requireSuccess(response);
    final decoded = _decodeMutationMap(
      response.body,
      resourceLabel: "inspection",
    );
    final remoteId = decoded["id"]?.toString();
    if (remoteId != operation.resourceId ||
        decoded["product_name"] != body["product_name"] ||
        decoded["product_identifier"] != body["product_identifier"]) {
      throw const SyncRequestFailure(
        statusCode: 409,
        apiCode: "remote_identity_mismatch",
        message:
            "Server inspection response does not match the queued resource.",
      );
    }

    return SyncExecutionSuccess(remoteResourceId: remoteId);
  }

  Future<SyncExecutionSuccess> _executeUploadCapture(
    SyncOperation operation,
  ) async {
    final payload = operation.payload;
    final captureId = _requiredString(payload, "capture_id");
    if (captureId != operation.resourceId) {
      throw StateError(
        "Capture payload ID does not match the queued resource ID.",
      );
    }

    final localPath = _requiredString(payload, "local_path");
    final expectedSha256 = _requiredString(payload, "sha256");
    final expectedSize = _requiredInt(payload, "size_bytes");
    final viewType = _requiredString(payload, "view_type");

    final file = File(localPath);
    if (!await file.exists()) {
      throw const SyncRequestFailure(
        statusCode: 409,
        apiCode: "local_evidence_missing",
        message: "Queued capture evidence is missing from local storage.",
      );
    }

    List<int> bytes;
    try {
      bytes = await file.readAsBytes();
    } on FileSystemException catch (error) {
      throw SyncRequestFailure(
        statusCode: 409,
        apiCode: "local_evidence_unavailable",
        message: error.message,
      );
    }

    final actualSha256 = sha256.convert(bytes).toString();
    if (bytes.length != expectedSize || actualSha256 != expectedSha256) {
      throw const SyncRequestFailure(
        statusCode: 409,
        apiCode: "local_evidence_integrity_failed",
        message:
            "Queued capture evidence no longer matches its persisted checksum.",
      );
    }

    final request = http.MultipartRequest(
      "POST",
      _endpoint(
        "api/v1/inspections/" +
            Uri.encodeComponent(operation.inspectionId) +
            "/captures",
      ),
    );
    request.headers.addAll(await _headers());
    request.fields["capture_id"] = captureId;
    request.fields["view_type"] = viewType;
    request.files.add(
      http.MultipartFile.fromBytes(
        "file",
        bytes,
        filename: p.basename(localPath),
      ),
    );

    final response = await _send(request);
    _requireSuccess(response);
    final decoded = _decodeMutationMap(
      response.body,
      resourceLabel: "capture",
    );
    final remoteId = decoded["id"]?.toString();
    if (remoteId != operation.resourceId ||
        decoded["inspection_id"]?.toString() != operation.inspectionId ||
        decoded["view_type"]?.toString() != viewType ||
        decoded["size_bytes"] != expectedSize) {
      throw const SyncRequestFailure(
        statusCode: 409,
        apiCode: "remote_identity_mismatch",
        message:
            "Server capture response does not match the queued resource.",
      );
    }

    final remoteSha256 = decoded["sha256"]?.toString();
    if (remoteSha256 != expectedSha256) {
      throw const SyncRequestFailure(
        statusCode: 409,
        apiCode: "remote_evidence_integrity_mismatch",
        message: "Server capture checksum does not match local evidence.",
      );
    }

    return SyncExecutionSuccess(remoteResourceId: remoteId);
  }

  Future<SyncExecutionSuccess> _executeProcessCapture(
    SyncOperation operation,
  ) async {
    final payload = operation.payload;
    final captureId = _requiredString(payload, "capture_id");
    final derivativeId = _requiredString(payload, "derivative_id");
    final qualityId = _requiredString(payload, "quality_assessment_id");
    if (qualityId != operation.resourceId) {
      throw StateError(
        "Preprocessing quality ID does not match the queued resource ID.",
      );
    }

    final request = http.Request(
      "POST",
      _endpoint(
        "api/v1/inspections/" +
            Uri.encodeComponent(operation.inspectionId) +
            "/captures/" +
            Uri.encodeComponent(captureId) +
            "/process",
      ),
    )
      ..headers.addAll(await _headers(json: true))
      ..body = jsonEncode(<String, Object?>{
        "derivative_id": derivativeId,
        "quality_assessment_id": qualityId,
      });

    final response = await _send(request);
    _requireSuccess(response);
    final decoded = _decodeMutationMap(
      response.body,
      resourceLabel: "capture preprocessing",
    );
    final derivative = _requiredResponseMap(
      decoded,
      "derivative",
      "capture preprocessing",
    );
    final quality = _requiredResponseMap(
      decoded,
      "quality",
      "capture preprocessing",
    );

    if (derivative["id"]?.toString() != derivativeId ||
        derivative["capture_id"]?.toString() != captureId ||
        quality["id"]?.toString() != qualityId ||
        quality["capture_id"]?.toString() != captureId ||
        quality["derivative_id"]?.toString() != derivativeId) {
      throw const SyncRequestFailure(
        statusCode: 409,
        apiCode: "remote_identity_mismatch",
        message:
            "Server preprocessing response does not match the queued resources.",
      );
    }

    return SyncExecutionSuccess(remoteResourceId: qualityId);
  }

  Future<SyncExecutionSuccess> _executeGeometry(
    SyncOperation operation,
  ) async {
    final payload = operation.payload;
    final captureId = _requiredString(payload, "capture_id");
    final geometryId = _requiredString(
      payload,
      "geometry_assessment_id",
    );
    final correctedCandidateId = _requiredString(
      payload,
      "corrected_derivative_id",
    );
    if (geometryId != operation.resourceId) {
      throw StateError(
        "Geometry assessment ID does not match the queued resource ID.",
      );
    }

    final request = http.Request(
      "POST",
      _endpoint(
        "api/v1/inspections/" +
            Uri.encodeComponent(operation.inspectionId) +
            "/captures/" +
            Uri.encodeComponent(captureId) +
            "/geometry/analyze",
      ),
    )
      ..headers.addAll(await _headers(json: true))
      ..body = jsonEncode(<String, Object?>{
        "geometry_assessment_id": geometryId,
        "corrected_derivative_id": correctedCandidateId,
      });

    final response = await _send(request);
    _requireSuccess(response);
    final decoded = _decodeMutationMap(
      response.body,
      resourceLabel: "geometry analysis",
    );
    _verifyGeometryResponse(
      decoded,
      captureId: captureId,
      geometryId: geometryId,
      correctedCandidateId: correctedCandidateId,
      uncertainOnMalformed: true,
    );

    return SyncExecutionSuccess(remoteResourceId: geometryId);
  }

  Future<SyncExecutionSuccess> _executeOcr(
    SyncOperation operation,
  ) async {
    final payload = operation.payload;
    final runId = _requiredString(payload, "id");
    final captureId = _requiredString(payload, "capture_id");
    if (runId != operation.resourceId) {
      throw StateError(
        "OCR run payload ID does not match the queued resource ID.",
      );
    }

    final request = http.Request(
      "POST",
      _endpoint(
        "api/v1/inspections/" +
            Uri.encodeComponent(operation.inspectionId) +
            "/captures/" +
            Uri.encodeComponent(captureId) +
            "/ocr/run",
      ),
    )
      ..headers.addAll(await _headers(json: true))
      ..body = jsonEncode(<String, Object?>{"id": runId});

    final response = await _send(request);
    _requireSuccess(response);
    final decoded = _decodeMutationMap(
      response.body,
      resourceLabel: "OCR run",
    );
    final run = _requiredResponseMap(decoded, "run", "OCR run");
    if (run["id"]?.toString() != runId ||
        run["capture_id"]?.toString() != captureId) {
      throw const SyncRequestFailure(
        statusCode: 409,
        apiCode: "remote_identity_mismatch",
        message: "Server OCR response does not match the queued run.",
      );
    }

    return SyncExecutionSuccess(remoteResourceId: runId);
  }

  Future<SyncExecutionSuccess> _executeDeclarationExtraction(
    SyncOperation operation,
  ) async {
    final runId = _requiredString(operation.payload, "id");
    if (runId != operation.resourceId) {
      throw StateError(
        "Declaration extraction payload ID does not match the queued resource ID.",
      );
    }

    final request = http.Request(
      "POST",
      _endpoint(
        "api/v1/inspections/" +
            Uri.encodeComponent(operation.inspectionId) +
            "/declarations/extract",
      ),
    )
      ..headers.addAll(await _headers(json: true))
      ..body = jsonEncode(<String, Object?>{"id": runId});

    final response = await _send(request);
    _requireSuccess(response);
    final decoded = _decodeMutationMap(
      response.body,
      resourceLabel: "declaration extraction",
    );
    final run = _requiredResponseMap(
      decoded,
      "run",
      "declaration extraction",
    );
    if (run["id"]?.toString() != runId ||
        run["inspection_id"]?.toString() != operation.inspectionId) {
      throw const SyncRequestFailure(
        statusCode: 409,
        apiCode: "remote_identity_mismatch",
        message:
            "Server declaration extraction response does not match the queued run.",
      );
    }

    return SyncExecutionSuccess(remoteResourceId: runId);
  }

  Future<SyncExecutionSuccess> _executeRuleEvaluation(
    SyncOperation operation,
  ) async {
    final runId = _requiredString(operation.payload, "id");
    final context = _requiredPayloadMap(operation.payload, "context");
    if (runId != operation.resourceId) {
      throw StateError(
        "Rule-evaluation payload ID does not match the queued resource ID.",
      );
    }

    final request = http.Request(
      "POST",
      _endpoint(
        "api/v1/inspections/" +
            Uri.encodeComponent(operation.inspectionId) +
            "/rule-evaluations/evaluate",
      ),
    )
      ..headers.addAll(await _headers(json: true))
      ..body = jsonEncode(<String, Object?>{
        "id": runId,
        "context": context,
      });

    final response = await _send(request);
    _requireSuccess(response);
    final decoded = _decodeMutationMap(
      response.body,
      resourceLabel: "rule evaluation",
    );
    final run = _requiredResponseMap(decoded, "run", "rule evaluation");
    if (run["id"]?.toString() != runId ||
        run["inspection_id"]?.toString() != operation.inspectionId ||
        canonicalJsonEncode(run["context_snapshot"]) !=
            canonicalJsonEncode(context)) {
      throw const SyncRequestFailure(
        statusCode: 409,
        apiCode: "remote_identity_mismatch",
        message:
            "Server rule-evaluation response does not match the queued run.",
      );
    }

    return SyncExecutionSuccess(remoteResourceId: runId);
  }

  Future<SyncExecutionSuccess> _executeOfficerReview(
    SyncOperation operation,
  ) async {
    final payload = operation.payload;
    final reviewId = _requiredString(payload, "id");
    if (reviewId != operation.resourceId) {
      throw StateError(
        "Officer review payload ID does not match the queued resource ID.",
      );
    }

    final resultId = _requiredString(
      payload,
      "rule_evaluation_result_id",
    );
    final body = <String, Object?>{
      "id": reviewId,
      "decision": _requiredString(payload, "decision"),
      if (payload.containsKey("corrected_value"))
        "corrected_value": payload["corrected_value"],
      if (payload.containsKey("note")) "note": payload["note"],
    };

    final request = http.Request(
      "POST",
      _endpoint(
        "api/v1/inspections/" +
            Uri.encodeComponent(operation.inspectionId) +
            "/rule-reviews/" +
            Uri.encodeComponent(resultId),
      ),
    )
      ..headers.addAll(await _headers(json: true))
      ..body = jsonEncode(body);

    final response = await _send(request);
    _requireSuccess(response);
    final decoded = _decodeMutationMap(
      response.body,
      resourceLabel: "Officer review",
    );
    final remoteId = decoded["id"]?.toString();
    if (remoteId != operation.resourceId ||
        decoded["inspection_id"]?.toString() != operation.inspectionId ||
        decoded["rule_evaluation_result_id"]?.toString() != resultId ||
        decoded["decision"]?.toString() != body["decision"] ||
        decoded["note"] != body["note"]) {
      throw const SyncRequestFailure(
        statusCode: 409,
        apiCode: "remote_identity_mismatch",
        message:
            "Server Officer review response does not match the queued resource.",
      );
    }

    if (body.containsKey("corrected_value") &&
        canonicalJsonEncode(decoded["corrected_value"]) !=
            canonicalJsonEncode(body["corrected_value"])) {
      throw const SyncRequestFailure(
        statusCode: 409,
        apiCode: "remote_identity_mismatch",
        message:
            "Server Officer correction does not match the queued correction.",
      );
    }

    return SyncExecutionSuccess(remoteResourceId: remoteId);
  }

  Future<ReconciliationResult> _reconcileInspection(
    SyncOperation operation,
  ) async {
    final response = await _get(
      "api/v1/inspections/" + Uri.encodeComponent(operation.resourceId),
    );
    if (response.statusCode == 404) {
      return const ReconciliationResult.notApplied();
    }
    _requireSuccess(response);

    final remote = _decodeReconciliationMap(
      response.body,
      resourceLabel: "inspection",
    );
    if (remote["id"]?.toString() != operation.resourceId) {
      return const ReconciliationResult.unresolved();
    }

    final expectedName = _requiredString(
      operation.payload,
      "product_name",
    );
    final expectedIdentifier = operation.payload["product_identifier"];
    if (remote["product_name"] != expectedName ||
        remote["product_identifier"] != expectedIdentifier) {
      return const ReconciliationResult.unresolved();
    }

    return ReconciliationResult.applied(
      remoteResourceId: operation.resourceId,
    );
  }

  Future<ReconciliationResult> _reconcileCapture(
    SyncOperation operation,
  ) async {
    final response = await _get(
      "api/v1/inspections/" +
          Uri.encodeComponent(operation.inspectionId) +
          "/captures",
    );
    if (response.statusCode == 404) {
      return const ReconciliationResult.notApplied();
    }
    _requireSuccess(response);

    final decoded = _decodeReconciliationList(
      response.body,
      resourceLabel: "capture list",
    );

    Map<String, dynamic>? remote;
    for (final item in decoded) {
      if (item is Map && item["id"]?.toString() == operation.resourceId) {
        remote = <String, dynamic>{
          for (final entry in item.entries)
            entry.key.toString(): entry.value,
        };
        break;
      }
    }

    if (remote == null) {
      return const ReconciliationResult.notApplied();
    }

    final expectedSha256 = _requiredString(
      operation.payload,
      "sha256",
    );
    final expectedSize = _requiredInt(
      operation.payload,
      "size_bytes",
    );
    final expectedView = _requiredString(
      operation.payload,
      "view_type",
    );

    if (remote["inspection_id"]?.toString() != operation.inspectionId ||
        remote["sha256"]?.toString() != expectedSha256 ||
        remote["size_bytes"] != expectedSize ||
        remote["view_type"]?.toString() != expectedView) {
      return const ReconciliationResult.unresolved();
    }

    return ReconciliationResult.applied(
      remoteResourceId: operation.resourceId,
    );
  }

  Future<ReconciliationResult> _reconcileProcessCapture(
    SyncOperation operation,
  ) async {
    final payload = operation.payload;
    final captureId = _requiredString(payload, "capture_id");
    final derivativeId = _requiredString(payload, "derivative_id");
    final qualityId = _requiredString(payload, "quality_assessment_id");

    final response = await _get(
      "api/v1/inspections/" +
          Uri.encodeComponent(operation.inspectionId) +
          "/captures/" +
          Uri.encodeComponent(captureId) +
          "/process-runs/" +
          Uri.encodeComponent(qualityId),
    );
    if (response.statusCode == 404) {
      return const ReconciliationResult.notApplied();
    }
    _requireSuccess(response);

    final decoded = _decodeReconciliationMap(
      response.body,
      resourceLabel: "capture preprocessing",
    );
    final derivative = _requiredReconciliationMap(
      decoded,
      "derivative",
      "capture preprocessing",
    );
    final quality = _requiredReconciliationMap(
      decoded,
      "quality",
      "capture preprocessing",
    );

    if (derivative["id"]?.toString() != derivativeId ||
        derivative["capture_id"]?.toString() != captureId ||
        quality["id"]?.toString() != qualityId ||
        quality["capture_id"]?.toString() != captureId ||
        quality["derivative_id"]?.toString() != derivativeId) {
      return const ReconciliationResult.unresolved();
    }

    return ReconciliationResult.applied(remoteResourceId: qualityId);
  }

  Future<ReconciliationResult> _reconcileGeometry(
    SyncOperation operation,
  ) async {
    final payload = operation.payload;
    final captureId = _requiredString(payload, "capture_id");
    final geometryId = _requiredString(
      payload,
      "geometry_assessment_id",
    );
    final correctedCandidateId = _requiredString(
      payload,
      "corrected_derivative_id",
    );

    final response = await _get(
      "api/v1/inspections/" +
          Uri.encodeComponent(operation.inspectionId) +
          "/captures/" +
          Uri.encodeComponent(captureId) +
          "/geometry/runs/" +
          Uri.encodeComponent(geometryId),
    );
    if (response.statusCode == 404) {
      return const ReconciliationResult.notApplied();
    }
    _requireSuccess(response);

    final decoded = _decodeReconciliationMap(
      response.body,
      resourceLabel: "geometry analysis",
    );
    final matches = _verifyGeometryResponse(
      decoded,
      captureId: captureId,
      geometryId: geometryId,
      correctedCandidateId: correctedCandidateId,
      uncertainOnMalformed: false,
    );
    return matches
        ? ReconciliationResult.applied(remoteResourceId: geometryId)
        : const ReconciliationResult.unresolved();
  }

  Future<ReconciliationResult> _reconcileOcr(
    SyncOperation operation,
  ) async {
    final runId = _requiredString(operation.payload, "id");
    final captureId = _requiredString(operation.payload, "capture_id");
    final response = await _get(
      "api/v1/inspections/" +
          Uri.encodeComponent(operation.inspectionId) +
          "/captures/" +
          Uri.encodeComponent(captureId) +
          "/ocr/runs/" +
          Uri.encodeComponent(runId),
    );
    if (response.statusCode == 404) {
      return const ReconciliationResult.notApplied();
    }
    _requireSuccess(response);

    final decoded = _decodeReconciliationMap(
      response.body,
      resourceLabel: "OCR run",
    );
    final run = _requiredReconciliationMap(decoded, "run", "OCR run");
    if (run["id"]?.toString() != runId ||
        run["capture_id"]?.toString() != captureId) {
      return const ReconciliationResult.unresolved();
    }

    return ReconciliationResult.applied(remoteResourceId: runId);
  }

  Future<ReconciliationResult> _reconcileDeclarationExtraction(
    SyncOperation operation,
  ) async {
    final runId = _requiredString(operation.payload, "id");
    final response = await _get(
      "api/v1/inspections/" +
          Uri.encodeComponent(operation.inspectionId) +
          "/declarations/runs/" +
          Uri.encodeComponent(runId),
    );
    if (response.statusCode == 404) {
      return const ReconciliationResult.notApplied();
    }
    _requireSuccess(response);

    final decoded = _decodeReconciliationMap(
      response.body,
      resourceLabel: "declaration extraction",
    );
    final run = _requiredReconciliationMap(
      decoded,
      "run",
      "declaration extraction",
    );
    if (run["id"]?.toString() != runId ||
        run["inspection_id"]?.toString() != operation.inspectionId) {
      return const ReconciliationResult.unresolved();
    }

    return ReconciliationResult.applied(remoteResourceId: runId);
  }

  Future<ReconciliationResult> _reconcileRuleEvaluation(
    SyncOperation operation,
  ) async {
    final runId = _requiredString(operation.payload, "id");
    final context = _requiredPayloadMap(operation.payload, "context");
    final response = await _get(
      "api/v1/inspections/" +
          Uri.encodeComponent(operation.inspectionId) +
          "/rule-evaluations/runs/" +
          Uri.encodeComponent(runId),
    );
    if (response.statusCode == 404) {
      return const ReconciliationResult.notApplied();
    }
    _requireSuccess(response);

    final decoded = _decodeReconciliationMap(
      response.body,
      resourceLabel: "rule evaluation",
    );
    final run = _requiredReconciliationMap(
      decoded,
      "run",
      "rule evaluation",
    );
    if (run["id"]?.toString() != runId ||
        run["inspection_id"]?.toString() != operation.inspectionId ||
        canonicalJsonEncode(run["context_snapshot"]) !=
            canonicalJsonEncode(context)) {
      return const ReconciliationResult.unresolved();
    }

    return ReconciliationResult.applied(remoteResourceId: runId);
  }

  Future<ReconciliationResult> _reconcileOfficerReview(
    SyncOperation operation,
  ) async {
    final response = await _get(
      "api/v1/inspections/" +
          Uri.encodeComponent(operation.inspectionId) +
          "/rule-reviews",
    );
    if (response.statusCode == 404) {
      return const ReconciliationResult.notApplied();
    }
    _requireSuccess(response);

    final decoded = _decodeReconciliationMap(
      response.body,
      resourceLabel: "Officer review history",
    );
    final reviews = decoded["reviews"];
    if (reviews is! List) {
      throw const SyncRequestFailure(
        statusCode: 502,
        apiCode: "invalid_reconciliation_response",
        message:
            "Officer review reconciliation response has no review list.",
      );
    }

    Map<String, dynamic>? remote;
    for (final item in reviews) {
      if (item is Map && item["id"]?.toString() == operation.resourceId) {
        remote = <String, dynamic>{
          for (final entry in item.entries)
            entry.key.toString(): entry.value,
        };
        break;
      }
    }

    if (remote == null) {
      return const ReconciliationResult.notApplied();
    }

    final expectedResultId = _requiredString(
      operation.payload,
      "rule_evaluation_result_id",
    );
    final expectedDecision = _requiredString(
      operation.payload,
      "decision",
    );
    final expectedNote = operation.payload["note"];

    if (remote["rule_evaluation_result_id"]?.toString() !=
            expectedResultId ||
        remote["decision"]?.toString() != expectedDecision ||
        remote["note"] != expectedNote) {
      return const ReconciliationResult.unresolved();
    }

    if (operation.payload.containsKey("corrected_value") &&
        canonicalJsonEncode(remote["corrected_value"]) !=
            canonicalJsonEncode(operation.payload["corrected_value"])) {
      return const ReconciliationResult.unresolved();
    }

    return ReconciliationResult.applied(
      remoteResourceId: operation.resourceId,
    );
  }

  Future<http.Response> _get(String path) async {
    final request = http.Request("GET", _endpoint(path))
      ..headers.addAll(await _headers());
    return _send(request);
  }

  Future<Map<String, String>> _headers({bool json = false}) async {
    final token = (await accessTokenProvider()).trim();
    if (token.isEmpty) {
      throw const SyncRequestFailure(
        statusCode: 401,
        apiCode: "local_auth_token_missing",
        message: "No access token is available for synchronization.",
      );
    }

    return <String, String>{
      "Authorization": "Bearer " + token,
      if (json) "Content-Type": "application/json",
      "Accept": "application/json",
    };
  }

  Uri _endpoint(String relativePath) {
    final normalizedBase = serverBaseUri.toString().endsWith("/")
        ? serverBaseUri
        : Uri.parse(serverBaseUri.toString() + "/");
    return normalizedBase.resolve(relativePath);
  }

  Future<http.Response> _send(http.BaseRequest request) async {
    try {
      final streamed = await client.send(request).timeout(requestTimeout);
      return await http.Response.fromStream(streamed).timeout(requestTimeout);
    } on TimeoutException {
      throw const SyncRequestFailure(
        timedOut: true,
        message: "The synchronization request timed out.",
      );
    } on http.ClientException catch (error) {
      throw SyncRequestFailure(
        transportUnavailable: true,
        message: error.message,
      );
    } on SocketException catch (error) {
      throw SyncRequestFailure(
        transportUnavailable: true,
        message: error.message,
      );
    }
  }

  void _requireSuccess(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return;
    }

    String? apiCode;
    String? message;
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is Map && decoded["error"] is Map) {
        final error = decoded["error"] as Map;
        apiCode = error["code"]?.toString();
        message = error["message"]?.toString();
      }
    } on FormatException {
      // Keep the protocol status even when the body is not JSON.
    }

    throw SyncRequestFailure(
      statusCode: response.statusCode,
      apiCode: apiCode,
      message: message ??
          "Synchronization request failed with HTTP " +
              response.statusCode.toString() +
              ".",
    );
  }

  bool _verifyGeometryResponse(
    Map<String, dynamic> response, {
    required String captureId,
    required String geometryId,
    required String correctedCandidateId,
    required bool uncertainOnMalformed,
  }) {
    final geometryValue = response["geometry"];
    if (geometryValue is! Map) {
      if (uncertainOnMalformed) {
        throw const SyncRequestFailure(
          apiCode: "response_unverifiable",
          message: "Server geometry success response has no geometry object.",
          outcomeUnknown: true,
        );
      }
      throw const SyncRequestFailure(
        statusCode: 502,
        apiCode: "invalid_reconciliation_response",
        message: "Geometry reconciliation response has no geometry object.",
      );
    }
    final geometry = <String, dynamic>{
      for (final entry in geometryValue.entries)
        entry.key.toString(): entry.value,
    };

    if (geometry["id"]?.toString() != geometryId ||
        geometry["capture_id"]?.toString() != captureId) {
      return false;
    }

    final correctedId = geometry["corrected_derivative_id"]?.toString();
    final correctedValue = response["corrected_derivative"];

    if (correctedId == null) {
      return correctedValue == null;
    }
    if (correctedId != correctedCandidateId || correctedValue is! Map) {
      return false;
    }

    final corrected = <String, dynamic>{
      for (final entry in correctedValue.entries)
        entry.key.toString(): entry.value,
    };
    return corrected["id"]?.toString() == correctedCandidateId &&
        corrected["capture_id"]?.toString() == captureId;
  }

  Map<String, Object?> _requiredPayloadMap(
    Map<String, Object?> payload,
    String key,
  ) {
    final value = payload[key];
    if (value is! Map) {
      throw StateError("Queued payload is missing required object: " + key);
    }
    return <String, Object?>{
      for (final entry in value.entries)
        entry.key.toString(): entry.value,
    };
  }

  Map<String, dynamic> _requiredResponseMap(
    Map<String, dynamic> response,
    String key,
    String resourceLabel,
  ) {
    final value = response[key];
    if (value is! Map) {
      throw SyncRequestFailure(
        apiCode: "response_unverifiable",
        message:
            "The server returned an unverifiable " +
            resourceLabel +
            " success response.",
        outcomeUnknown: true,
      );
    }
    return <String, dynamic>{
      for (final entry in value.entries)
        entry.key.toString(): entry.value,
    };
  }

  Map<String, dynamic> _requiredReconciliationMap(
    Map<String, dynamic> response,
    String key,
    String resourceLabel,
  ) {
    final value = response[key];
    if (value is! Map) {
      throw SyncRequestFailure(
        statusCode: 502,
        apiCode: "invalid_reconciliation_response",
        message:
            "The server returned an invalid " +
            resourceLabel +
            " reconciliation response.",
      );
    }
    return <String, dynamic>{
      for (final entry in value.entries)
        entry.key.toString(): entry.value,
    };
  }

  Map<String, dynamic> _decodeMutationMap(
    String body, {
    required String resourceLabel,
  }) {
    try {
      return _decodeMap(body);
    } on FormatException catch (error) {
      throw SyncRequestFailure(
        apiCode: "response_unverifiable",
        message:
            "The server returned an unverifiable " +
            resourceLabel +
            " success response: " +
            error.message,
        outcomeUnknown: true,
      );
    }
  }

  Map<String, dynamic> _decodeReconciliationMap(
    String body, {
    required String resourceLabel,
  }) {
    try {
      return _decodeMap(body);
    } on FormatException catch (error) {
      throw SyncRequestFailure(
        statusCode: 502,
        apiCode: "invalid_reconciliation_response",
        message:
            "The server returned an invalid " +
            resourceLabel +
            " reconciliation response: " +
            error.message,
      );
    }
  }

  List<dynamic> _decodeReconciliationList(
    String body, {
    required String resourceLabel,
  }) {
    try {
      final decoded = jsonDecode(body);
      if (decoded is! List) {
        throw const FormatException("Expected a JSON array response.");
      }
      return decoded;
    } on FormatException catch (error) {
      throw SyncRequestFailure(
        statusCode: 502,
        apiCode: "invalid_reconciliation_response",
        message:
            "The server returned an invalid " +
            resourceLabel +
            " reconciliation response: " +
            error.message,
      );
    }
  }

  Map<String, dynamic> _decodeMap(String body) {
    final decoded = jsonDecode(body);
    if (decoded is! Map) {
      throw const FormatException("Expected a JSON object response.");
    }
    return <String, dynamic>{
      for (final entry in decoded.entries)
        entry.key.toString(): entry.value,
    };
  }

  String _requiredString(
    Map<String, Object?> payload,
    String key,
  ) {
    final value = payload[key];
    if (value is! String || value.isEmpty) {
      throw StateError("Queued payload is missing required string: " + key);
    }
    return value;
  }

  int _requiredInt(
    Map<String, Object?> payload,
    String key,
  ) {
    final value = payload[key];
    if (value is! int) {
      throw StateError("Queued payload is missing required integer: " + key);
    }
    return value;
  }
}
