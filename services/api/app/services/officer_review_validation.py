from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.errors import unprocessable

_MAX_DECIMAL_ADJUSTED_EXPONENT = 18


def _invalid_decimal(field_name: str):
    return unprocessable(
        "invalid_corrected_value",
        f"{field_name} must be a positive decimal value within the supported numeric range.",
    )


def _require_exact_keys(value: dict, expected: set[str]) -> None:
    if set(value) != expected:
        raise unprocessable(
            "invalid_corrected_value",
            f"Corrected value must contain exactly: {', '.join(sorted(expected))}.",
        )


def _positive_decimal(raw: object, *, field_name: str) -> Decimal:
    if isinstance(raw, bool):
        raise _invalid_decimal(field_name)

    try:
        parsed = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        raise _invalid_decimal(field_name)

    if (
        not parsed.is_finite()
        or parsed <= 0
        or abs(parsed.adjusted()) > _MAX_DECIMAL_ADJUSTED_EXPONENT
    ):
        raise _invalid_decimal(field_name)

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
        try:
            normalized_amount = amount.quantize(Decimal("0.01"))
        except InvalidOperation:
            raise _invalid_decimal("amount")

        return {
            "currency": "INR",
            "amount": format(normalized_amount, ".2f"),
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
