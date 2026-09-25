class OfficerReviewState {
  const OfficerReviewState({
    required this.inspectionId,
    required this.status,
    required this.results,
    required this.latestReviews,
    this.finalizationId,
    this.reportId,
  });

  final String inspectionId;
  final String status;
  final List<OfficerRuleResult> results;
  final Map<String, OfficerRuleReview> latestReviews;
  final String? finalizationId;
  final String? reportId;

  bool get isPendingReview => status == "pending_review";
  bool get isFinalized => status == "finalized";

  bool get canFinalize {
    if (!isPendingReview || results.isEmpty) {
      return false;
    }
    for (final result in results) {
      final review = latestReviews[result.id];
      if (review == null || !result.isResolvedBy(review)) {
        return false;
      }
    }
    return true;
  }
}

class OfficerRuleResult {
  const OfficerRuleResult({
    required this.id,
    required this.ruleId,
    required this.provision,
    required this.declarationType,
    required this.status,
    required this.explanation,
  });

  final String id;
  final String ruleId;
  final String provision;
  final String declarationType;
  final String status;
  final String explanation;

  bool get supportsCorrection =>
      declarationType == "mrp" || declarationType == "net_quantity";

  bool get canAccept => status == "pass";

  bool get canCorrect =>
      supportsCorrection &&
      (status == "pass" || status == "manual_verification_required");

  bool isResolvedBy(OfficerRuleReview review) {
    if (review.decision == "recheck_required") {
      return false;
    }
    if (review.decision == "accepted") {
      return status == "pass";
    }
    if (review.decision == "corrected") {
      return canCorrect && review.correctedValue != null;
    }
    return false;
  }
}

class OfficerRuleReview {
  const OfficerRuleReview({
    required this.id,
    required this.ruleEvaluationResultId,
    required this.decision,
    required this.revision,
    this.correctedValue,
    this.note,
  });

  final String id;
  final String ruleEvaluationResultId;
  final String decision;
  final int revision;
  final Map<String, Object?>? correctedValue;
  final String? note;
}
