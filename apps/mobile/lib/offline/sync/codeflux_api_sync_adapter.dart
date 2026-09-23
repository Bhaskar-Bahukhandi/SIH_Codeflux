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
    final decoded = _decodeMap(response.body);
    final remoteId = decoded["id"]?.toString();
    if (remoteId != operation.resourceId) {
      throw const SyncRequestFailure(
        statusCode: 409,
        apiCode: "remote_identity_mismatch",
        message: "Server returned a different inspection ID.",
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
    final decoded = _decodeMap(response.body);
    final remoteId = decoded["id"]?.toString();
    if (remoteId != operation.resourceId) {
      throw const SyncRequestFailure(
        statusCode: 409,
        apiCode: "remote_identity_mismatch",
        message: "Server returned a different capture ID.",
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
    final decoded = _decodeMap(response.body);
    final remoteId = decoded["id"]?.toString();
    if (remoteId != operation.resourceId) {
      throw const SyncRequestFailure(
        statusCode: 409,
        apiCode: "remote_identity_mismatch",
        message: "Server returned a different Officer review ID.",
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

    final remote = _decodeMap(response.body);
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

    final decoded = jsonDecode(response.body);
    if (decoded is! List) {
      throw const FormatException(
        "Capture reconciliation response is not a JSON array.",
      );
    }

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

    if (remote["sha256"]?.toString() != expectedSha256 ||
        remote["size_bytes"] != expectedSize ||
        remote["view_type"]?.toString() != expectedView) {
      return const ReconciliationResult.unresolved();
    }

    return ReconciliationResult.applied(
      remoteResourceId: operation.resourceId,
    );
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

    final decoded = _decodeMap(response.body);
    final reviews = decoded["reviews"];
    if (reviews is! List) {
      throw const FormatException(
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
