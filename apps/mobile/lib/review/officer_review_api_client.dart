import "dart:convert";

import "package:http/http.dart" as http;

import "../auth/officer_session_store.dart";
import "officer_review_models.dart";

class OfficerReviewApiClient {
  const OfficerReviewApiClient({
    required this.client,
    required this.serverBaseUri,
    required this.sessionStore,
    this.requestTimeout = const Duration(seconds: 20),
  });

  final http.Client client;
  final Uri serverBaseUri;
  final OfficerSessionStore sessionStore;
  final Duration requestTimeout;

  Future<OfficerReviewState> load(String inspectionId) async {
    final inspection = await _getMap(
      "api/v1/inspections/" + Uri.encodeComponent(inspectionId),
    );
    final status = inspection["status"]?.toString();
    if (status == null || status.isEmpty) {
      throw const FormatException("Inspection response has no status.");
    }

    if (status != "pending_review" && status != "finalized") {
      return OfficerReviewState(
        inspectionId: inspectionId,
        status: status,
        results: const <OfficerRuleResult>[],
        latestReviews: const <String, OfficerRuleReview>{},
      );
    }

    final evaluation = await _getMap(
      "api/v1/inspections/" +
          Uri.encodeComponent(inspectionId) +
          "/rule-evaluations/latest",
    );
    final rawResults = evaluation["results"];
    if (rawResults is! List) {
      throw const FormatException(
        "Rule evaluation response has no result list.",
      );
    }

    final results = rawResults.map((value) {
      if (value is! Map) {
        throw const FormatException("Rule result is not an object.");
      }
      return OfficerRuleResult(
        id: _requiredString(value, "id"),
        ruleId: _requiredString(value, "rule_id"),
        provision: _requiredString(value, "provision"),
        declarationType: _requiredString(value, "declaration_type"),
        status: _requiredString(value, "status"),
        explanation: _requiredString(value, "explanation"),
      );
    }).toList(growable: false);

    final reviewHistory = await _getMap(
      "api/v1/inspections/" +
          Uri.encodeComponent(inspectionId) +
          "/rule-reviews",
    );
    final rawLatest = reviewHistory["latest_by_rule_result"];
    if (rawLatest is! Map) {
      throw const FormatException(
        "Officer review response has no latest-review map.",
      );
    }

    final latestReviews = <String, OfficerRuleReview>{};
    for (final entry in rawLatest.entries) {
      final value = entry.value;
      if (value is! Map) {
        continue;
      }
      final corrected = value["corrected_value"];
      latestReviews[entry.key.toString()] = OfficerRuleReview(
        id: _requiredString(value, "id"),
        ruleEvaluationResultId: _requiredString(
          value,
          "rule_evaluation_result_id",
        ),
        decision: _requiredString(value, "decision"),
        revision: _requiredInt(value, "revision"),
        correctedValue: corrected is Map
            ? <String, Object?>{
                for (final item in corrected.entries)
                  item.key.toString(): item.value,
              }
            : null,
        note: value["note"]?.toString(),
      );
    }

    String? finalizationId;
    String? reportId;
    if (status == "finalized") {
      final finalization = await _getMap(
        "api/v1/inspections/" +
            Uri.encodeComponent(inspectionId) +
            "/finalization",
      );
      finalizationId = finalization["id"]?.toString();
      reportId = finalization["report_id"]?.toString();
    }

    return OfficerReviewState(
      inspectionId: inspectionId,
      status: status,
      results: List<OfficerRuleResult>.unmodifiable(results),
      latestReviews: Map<String, OfficerRuleReview>.unmodifiable(
        latestReviews,
      ),
      finalizationId: finalizationId,
      reportId: reportId,
    );
  }

  Future<Map<String, dynamic>> _getMap(String path) async {
    final token = await sessionStore.readValidAccessToken();
    if (token == null || token.trim().isEmpty) {
      throw StateError("Officer session has expired. Sign in again.");
    }

    final request = http.Request("GET", _endpoint(path))
      ..headers.addAll(<String, String>{
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
      });

    final streamed = await client.send(request).timeout(requestTimeout);
    final response =
        await http.Response.fromStream(streamed).timeout(requestTimeout);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw StateError(_errorMessage(response));
    }

    final decoded = jsonDecode(response.body);
    if (decoded is! Map) {
      throw const FormatException("Server response is not a JSON object.");
    }
    return <String, dynamic>{
      for (final entry in decoded.entries)
        entry.key.toString(): entry.value,
    };
  }

  String _errorMessage(http.Response response) {
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is Map) {
        final error = decoded["error"];
        if (error is Map && error["message"] != null) {
          return error["message"].toString();
        }
        if (decoded["detail"] != null) {
          return decoded["detail"].toString();
        }
      }
    } catch (_) {
      // Fall through to the status-only message.
    }
    return "Server request failed with HTTP ${response.statusCode}.";
  }

  Uri _endpoint(String relativePath) {
    final normalizedBase = serverBaseUri.toString().endsWith("/")
        ? serverBaseUri
        : Uri.parse(serverBaseUri.toString() + "/");
    return normalizedBase.resolve(relativePath);
  }

  static String _requiredString(Map value, String key) {
    final item = value[key];
    if (item is! String || item.trim().isEmpty) {
      throw FormatException("Missing required field: " + key);
    }
    return item;
  }

  static int _requiredInt(Map value, String key) {
    final item = value[key];
    if (item is int) {
      return item;
    }
    throw FormatException("Missing required integer field: " + key);
  }
}
