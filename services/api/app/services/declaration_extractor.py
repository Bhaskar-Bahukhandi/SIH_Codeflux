from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from statistics import mean

from app.models.declaration import DeclarationType

DECLARATION_EXTRACTOR_VERSION = "declaration-extractor-v1"
SUPPORTED_DECLARATION_TYPES = (
    DeclarationType.MRP,
    DeclarationType.NET_QUANTITY,
)

_MRP = re.compile(
    r"\b(?:m\.?\s*r\.?\s*p\.?|maximum\s+retail\s+price|"
    r"retail\s+sale\s+price)\s*[:\-]?\s*"
    r"(?:rs\.?|inr|₹)?\s*"
    r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)

_NET_QUANTITY = re.compile(
    r"\bnet\s*(?:qty|quantity|wt|weight|content)\.?\s*[:\-]?\s*"
    r"([0-9]+(?:\.[0-9]+)?)\s*"
    r"(kg|kgs|kilogram|kilograms|g|gm|gms|gram|grams|"
    r"ml|millilitre|millilitres|milliliter|milliliters|"
    r"l|ltr|ltrs|litre|litres|liter|liters)\b",
    re.IGNORECASE,
)

_UNIT_MAP = {
    "kg": "kg",
    "kgs": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "g": "g",
    "gm": "g",
    "gms": "g",
    "gram": "g",
    "grams": "g",
    "ml": "ml",
    "millilitre": "ml",
    "millilitres": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "l": "l",
    "ltr": "l",
    "ltrs": "l",
    "litre": "l",
    "litres": "l",
    "liter": "l",
    "liters": "l",
}


@dataclass(frozen=True, slots=True)
class OcrTextEvidence:
    block_id: str
    order_index: int
    text: str
    confidence: float


@dataclass(frozen=True, slots=True)
class ExtractedDeclaration:
    declaration_type: DeclarationType
    raw_text: str
    normalized_value: dict
    block_ids: list[str]
    ocr_confidence_min: float
    ocr_confidence_mean: float
    extractor_method: str


def _decimal_string(value: str) -> str | None:
    try:
        parsed = Decimal(value.replace(",", ""))
    except InvalidOperation:
        return None
    if not parsed.is_finite():
        return None

    normalized = format(parsed.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _extract_mrp(text: str) -> tuple[dict, str] | None:
    match = _MRP.search(text)
    if match is None:
        return None

    try:
        amount = Decimal(match.group(1).replace(",", "")).quantize(
            Decimal("0.01")
        )
    except InvalidOperation:
        return None

    return (
        {
            "currency": "INR",
            "amount": format(amount, ".2f"),
        },
        "mrp_label_v1",
    )


def _extract_net_quantity(text: str) -> tuple[dict, str] | None:
    match = _NET_QUANTITY.search(text)
    if match is None:
        return None

    value = _decimal_string(match.group(1))
    if value is None:
        return None

    unit = _UNIT_MAP.get(match.group(2).lower())
    if unit is None:
        return None

    return (
        {
            "value": value,
            "unit": unit,
        },
        "net_quantity_label_v1",
    )


def _extract_type(
    declaration_type: DeclarationType,
    text: str,
) -> tuple[dict, str] | None:
    if declaration_type is DeclarationType.MRP:
        return _extract_mrp(text)
    if declaration_type is DeclarationType.NET_QUANTITY:
        return _extract_net_quantity(text)
    return None


def extract_declarations(
    blocks: list[OcrTextEvidence],
) -> list[ExtractedDeclaration]:
    ordered = sorted(blocks, key=lambda block: block.order_index)
    extracted: list[ExtractedDeclaration] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()

    for index, block in enumerate(ordered):
        for declaration_type in SUPPORTED_DECLARATION_TYPES:
            matched = _extract_type(declaration_type, block.text)
            evidence = [block]

            if matched is None and index + 1 < len(ordered):
                next_block = ordered[index + 1]
                combined = f"{block.text} {next_block.text}"
                matched = _extract_type(declaration_type, combined)
                if matched is not None:
                    evidence = [block, next_block]

            if matched is None:
                continue

            normalized_value, method = matched
            key = (
                declaration_type.value,
                json.dumps(
                    normalized_value,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                tuple(item.block_id for item in evidence),
            )
            if key in seen:
                continue
            seen.add(key)

            confidences = [item.confidence for item in evidence]
            extracted.append(
                ExtractedDeclaration(
                    declaration_type=declaration_type,
                    raw_text=" | ".join(item.text for item in evidence),
                    normalized_value=normalized_value,
                    block_ids=[item.block_id for item in evidence],
                    ocr_confidence_min=round(min(confidences), 6),
                    ocr_confidence_mean=round(mean(confidences), 6),
                    extractor_method=method,
                )
            )

    return extracted
