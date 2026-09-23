from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import conflict, unprocessable
from app.models.capture import Capture
from app.models.finding_review import (
    OfficerReviewDecision,
    OfficerReviewOutcome,
)
from app.models.rule_evaluation import (
    RuleEvaluationResult,
    RuleEvaluationStatus,
)

_REVIEWABLE_MACHINE_STATUSES = {
    RuleEvaluationStatus.PASS,
    RuleEvaluationStatus.MANUAL_VERIFICATION_REQUIRED,
}
_QUANTITY_UNITS = {"g", "kg", "ml", "l"}


def _positive_decimal(value: object, *, field_name: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise unprocessable(
            "invalid_corrected_value",
            f"{field_name} must be a positive decimal value.",
        )
    if not parsed.is_finite() or parsed <= 0:
        raise unprocessable(
            "invalid_corrected_value",
            f"{field_name} must be a positive decimal value.",
        )
    return parsed


def normalize_corrected_value(
    *,
    declaration_type: str,
    value: dict,
) -> dict:
    if declaration_type == "mrp":
        if set(value) != {"currency", "amount"}:
            raise unprocessable(
                "invalid_corrected_value",
                "MRP correction must contain exactly currency and amount.",
            )
        currency = str(value["currency"]).strip().upper()
        if currency != "INR":
            raise unprocessable(
                "invalid_corrected_value",
                "The current MRP correction format supports INR only.",
            )
        amount = _positive_decimal(value["amount"], field_name="amount")
        return {
            "currency": "INR",
            "amount": format(amount.quantize(Decimal("0.01")), ".2f"),
        }

    if declaration_type == "net_quantity":
        if set(value) != {"value", "unit"}:
            raise unprocessable(
                "invalid_corrected_value",
                "Net-quantity correction must contain exactly value and unit.",
            )
        quantity = _positive_decimal(value["value"], field_name="value")
        unit = str(value["unit"]).strip().lower()
        if unit not in _QUANTITY_UNITS:
            raise unprocessable(
                "invalid_corrected_value",
                "The current net-quantity correction format supports g, kg, ml and l.",
            )
        normalized = format(quantity.normalize(), "f")
        if "." in normalized:
            normalized = normalized.rstrip("0").rstrip(".")
        return {
            "value": normalized,
            "unit": unit,
        }

    raise unprocessable(
        "unsupported_review_declaration",
        "This declaration type does not support structured correction yet.",
    )


def validate_evidence_captures(
    db: Session,
    *,
    inspection_id: str,
    capture_ids: list[str],
) -> None:
    if not capture_ids:
        return

    found = set(
        db.scalars(
            select(Capture.id).where(
                Capture.inspection_id == inspection_id,
                Capture.id.in_(capture_ids),
            )
        ).all()
    )
    if found != set(capture_ids):
        raise unprocessable(
            "invalid_review_evidence",
            "Every evidence capture must belong to the reviewed inspection.",
        )


def resolve_review(
    *,
    machine_result: RuleEvaluationResult,
    decision: OfficerReviewDecision,
    corrected_value: dict | None,
    evidence_capture_ids: list[str],
    note: str | None,
) -> tuple[OfficerReviewOutcome, dict | None]:
    if machine_result.status not in _REVIEWABLE_MACHINE_STATUSES:
        raise conflict(
            "rule_result_not_reviewable",
            "Resolve applicability/context and rerun the rule evaluation before reviewing this result.",
        )

    if decision is OfficerReviewDecision.REQUEST_RECHECK:
        if corrected_value is not None:
            raise unprocessable(
                "invalid_review_payload",
                "A recheck request cannot include a corrected value.",
            )
        if not note:
            raise unprocessable(
                "review_note_required",
                "A recheck request requires an officer note.",
            )
        return OfficerReviewOutcome.RECHECK_REQUIRED, None

    if not evidence_capture_ids:
        raise unprocessable(
            "review_evidence_required",
            "This officer decision requires at least one inspection capture as evidence.",
        )

    if decision is OfficerReviewDecision.CONFIRM_PRESENT:
        if corrected_value is not None:
            raise unprocessable(
                "invalid_review_payload",
                "Confirm-present review cannot include a corrected value.",
            )
        return OfficerReviewOutcome.VERIFIED_DECLARATION_PRESENT, None

    if decision is OfficerReviewDecision.CONFIRM_ABSENT:
        if corrected_value is not None:
            raise unprocessable(
                "invalid_review_payload",
                "Confirm-absent review cannot include a corrected value.",
            )
        if not note:
            raise unprocessable(
                "review_note_required",
                "Confirmed absence requires an officer note.",
            )
        return OfficerReviewOutcome.POTENTIAL_NON_COMPLIANCE, None

    if decision is OfficerReviewDecision.CORRECT_VALUE:
        if corrected_value is None:
            raise unprocessable(
                "corrected_value_required",
                "A corrected-value review requires corrected_value.",
            )
        if not note:
            raise unprocessable(
                "review_note_required",
                "A corrected-value review requires an officer note.",
            )
        normalized = normalize_corrected_value(
            declaration_type=machine_result.declaration_type,
            value=corrected_value,
        )
        return OfficerReviewOutcome.VERIFIED_DECLARATION_PRESENT, normalized

    raise unprocessable(
        "invalid_review_decision",
        "Unsupported officer review decision.",
    )
