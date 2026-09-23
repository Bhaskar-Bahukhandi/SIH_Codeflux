from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.errors import unprocessable


def _require_exact_keys(value: dict, expected: set[str]) -> None:
    if set(value) != expected:
        raise unprocessable(
            "invalid_corrected_value",
            f"Corrected value must contain exactly: {', '.join(sorted(expected))}.",
        )


def _positive_decimal(raw: object, *, field_name: str) -> Decimal:
    if isinstance(raw, bool):
        raise unprocessable(
            "invalid_corrected_value",
            f"{field_name} must be a positive decimal value.",
        )

    try:
        parsed = Decimal(str(raw))
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


def normalize_officer_corrected_value(
    *,
    declaration_type: str,
    value: dict,
) -> dict:
    if declaration_type == "mrp":
        _require_exact_keys(value, {"currency", "amount"})
        currency = str(value["currency"]).strip().upper()
        if currency != "INR":
            raise unprocessable(
                "invalid_corrected_value",
                "MRP correction currency must be INR.",
            )

        amount = _positive_decimal(value["amount"], field_name="amount")
        return {
            "currency": "INR",
            "amount": format(amount.quantize(Decimal("0.01")), ".2f"),
        }

    if declaration_type == "net_quantity":
        _require_exact_keys(value, {"value", "unit"})
        quantity = _positive_decimal(value["value"], field_name="value")
        unit = str(value["unit"]).strip().lower()
        if unit not in {"g", "kg", "ml", "l"}:
            raise unprocessable(
                "invalid_corrected_value",
                "Net-quantity correction unit must be one of: g, kg, ml, l.",
            )

        normalized = format(quantity.normalize(), "f")
        if "." in normalized:
            normalized = normalized.rstrip("0").rstrip(".")

        return {
            "value": normalized,
            "unit": unit,
        }

    raise unprocessable(
        "unsupported_corrected_value",
        "This rule result does not support a structured officer correction.",
    )
