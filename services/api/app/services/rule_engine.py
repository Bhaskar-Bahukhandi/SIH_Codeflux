from __future__ import annotations

from dataclasses import dataclass

from app.models.declaration import (
    DeclarationFusionStatus,
    DeclarationSummary,
)
from app.models.rule_evaluation import RuleEvaluationStatus
from app.schemas.rule_evaluation import RuleEvaluationContextInput
from app.services.rule_pack import LoadedRulePack, RuleDefinition


@dataclass(frozen=True, slots=True)
class EvaluatedRule:
    rule: RuleDefinition
    status: RuleEvaluationStatus
    evidence_summary_id: str | None
    explanation: str
    details: dict


def _scope_status(
    context: RuleEvaluationContextInput,
    rule_pack: LoadedRulePack,
) -> tuple[RuleEvaluationStatus | None, str | None]:
    if context.intended_for_retail_sale is False:
        return (
            RuleEvaluationStatus.NOT_EVALUATED,
            "This rule pack is limited to packages confirmed as intended for retail sale.",
        )
    if context.industrial_or_institutional_consumer is True:
        return (
            RuleEvaluationStatus.NOT_EVALUATED,
            "Industrial/institutional consumer packages are outside this rule pack's supported scope.",
        )
    if context.package_exceeds_25kg_or_25l is True:
        return (
            RuleEvaluationStatus.NOT_EVALUATED,
            "Packages above the first rule pack's supported 25 kg / 25 L profile are not evaluated.",
        )

    values = (
        context.intended_for_retail_sale,
        context.industrial_or_institutional_consumer,
        context.package_exceeds_25kg_or_25l,
    )
    if any(value is None for value in values):
        return (
            RuleEvaluationStatus.INDETERMINATE,
            "Applicability context is incomplete; officer confirmation is required before this rule pack can evaluate the declaration evidence.",
        )

    supported = rule_pack.definition.supported_scope
    if (
        context.intended_for_retail_sale != supported.intended_for_retail_sale
        or context.industrial_or_institutional_consumer
        != supported.industrial_or_institutional_consumer
        or context.package_exceeds_25kg_or_25l
        != supported.package_exceeds_25kg_or_25l
    ):
        return (
            RuleEvaluationStatus.NOT_EVALUATED,
            "The supplied context is outside this rule pack's supported profile.",
        )

    return None, None


def evaluate_rules(
    *,
    rule_pack: LoadedRulePack,
    context: RuleEvaluationContextInput,
    summaries: dict[str, DeclarationSummary],
) -> list[EvaluatedRule]:
    scope_status, scope_explanation = _scope_status(context, rule_pack)
    evaluated: list[EvaluatedRule] = []

    for rule in rule_pack.definition.rules:
        if scope_status is not None:
            evaluated.append(
                EvaluatedRule(
                    rule=rule,
                    status=scope_status,
                    evidence_summary_id=None,
                    explanation=scope_explanation or "Rule not evaluated.",
                    details={
                        "supported_scope": rule_pack.definition.supported_scope.model_dump(),
                    },
                )
            )
            continue

        summary = summaries.get(rule.declaration_type.value)
        if summary is None:
            evaluated.append(
                EvaluatedRule(
                    rule=rule,
                    status=RuleEvaluationStatus.INDETERMINATE,
                    evidence_summary_id=None,
                    explanation=(
                        "The current extraction run does not contain the declaration summary "
                        "required by this rule."
                    ),
                    details={},
                )
            )
            continue

        details = {
            "declaration_fusion_status": summary.status.value,
            "candidate_values": summary.candidate_values,
            "observation_count": summary.observation_count,
            "capture_count": summary.capture_count,
        }

        if summary.status in {
            DeclarationFusionStatus.SINGLE_SOURCE,
            DeclarationFusionStatus.CONSISTENT,
        }:
            status = RuleEvaluationStatus.PASS
            explanation = (
                "Current structured evidence contains a detected declaration value. "
                "This passes the preliminary declaration-evidence check only; it is not "
                "a final legal-compliance determination."
            )
        elif summary.status is DeclarationFusionStatus.CONFLICT:
            status = RuleEvaluationStatus.MANUAL_VERIFICATION_REQUIRED
            explanation = (
                "Current package views contain conflicting normalized declaration values. "
                "An officer must review the source evidence; no value is selected automatically."
            )
        else:
            status = RuleEvaluationStatus.MANUAL_VERIFICATION_REQUIRED
            explanation = (
                "The current extractor did not detect this declaration. OCR/extraction "
                "non-detection is not proof of physical absence or non-compliance; officer "
                "verification is required."
            )

        evaluated.append(
            EvaluatedRule(
                rule=rule,
                status=status,
                evidence_summary_id=summary.id,
                explanation=explanation,
                details=details,
            )
        )

    return evaluated
