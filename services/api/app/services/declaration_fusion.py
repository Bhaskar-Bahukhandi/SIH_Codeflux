from __future__ import annotations

import json
from dataclasses import dataclass

from app.models.declaration import (
    DeclarationFusionStatus,
    DeclarationType,
)
from app.services.declaration_extractor import SUPPORTED_DECLARATION_TYPES

DECLARATION_FUSION_VERSION = "fusion-v1"


@dataclass(frozen=True, slots=True)
class FusionObservation:
    declaration_type: DeclarationType
    capture_id: str
    normalized_value: dict


@dataclass(frozen=True, slots=True)
class FusedDeclaration:
    declaration_type: DeclarationType
    status: DeclarationFusionStatus
    canonical_value: dict | None
    candidate_values: list[dict]
    observation_count: int
    capture_count: int


def _value_key(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def fuse_declarations(
    observations: list[FusionObservation],
) -> list[FusedDeclaration]:
    fused: list[FusedDeclaration] = []

    for declaration_type in SUPPORTED_DECLARATION_TYPES:
        relevant = [
            observation
            for observation in observations
            if observation.declaration_type is declaration_type
        ]
        distinct_captures = {observation.capture_id for observation in relevant}

        values_by_key: dict[str, dict] = {}
        for observation in relevant:
            values_by_key.setdefault(
                _value_key(observation.normalized_value),
                observation.normalized_value,
            )

        candidate_values = [
            values_by_key[key]
            for key in sorted(values_by_key)
        ]

        if not relevant:
            status = DeclarationFusionStatus.NOT_DETECTED
            canonical_value = None
        elif len(candidate_values) > 1:
            status = DeclarationFusionStatus.CONFLICT
            canonical_value = None
        elif len(distinct_captures) >= 2:
            status = DeclarationFusionStatus.CONSISTENT
            canonical_value = candidate_values[0]
        else:
            status = DeclarationFusionStatus.SINGLE_SOURCE
            canonical_value = candidate_values[0]

        fused.append(
            FusedDeclaration(
                declaration_type=declaration_type,
                status=status,
                canonical_value=canonical_value,
                candidate_values=candidate_values,
                observation_count=len(relevant),
                capture_count=len(distinct_captures),
            )
        )

    return fused
