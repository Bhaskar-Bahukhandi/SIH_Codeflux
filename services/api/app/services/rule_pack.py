from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from app.models.declaration import DeclarationType

RULE_PACK_PATH = (
    Path(__file__).resolve().parents[4]
    / "packages"
    / "rulepacks"
    / "lmpc-retail-evidence-v1.json"
)


class RulePackScope(BaseModel):
    intended_for_retail_sale: bool
    industrial_or_institutional_consumer: bool
    package_exceeds_25kg_or_25l: bool


class RulePackSource(BaseModel):
    source_id: str
    title: str
    kind: str
    url: str
    checked_on: date


class RuleDefinition(BaseModel):
    rule_id: str
    provision: str
    effective_from: date
    declaration_type: DeclarationType
    check_type: str
    source_ids: list[str] = Field(min_length=1)
    applicability_note: str = Field(min_length=1)
    summary: str = Field(min_length=1)


class RulePackDefinition(BaseModel):
    schema_version: int
    rule_pack_id: str
    version: str
    jurisdiction: str
    authority: str
    verified_on: date
    reviewed_by: str = Field(min_length=1)
    review_type: str = Field(min_length=1)
    purpose: str
    supported_scope: RulePackScope
    sources: list[RulePackSource] = Field(min_length=1)
    rules: list[RuleDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> "RulePackDefinition":
        source_ids = [source.source_id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Rule pack contains duplicate source IDs.")

        rule_ids = [rule.rule_id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("Rule pack contains duplicate rule IDs.")

        known_sources = set(source_ids)
        for rule in self.rules:
            unknown = set(rule.source_ids) - known_sources
            if unknown:
                raise ValueError(
                    f"Rule {rule.rule_id} references unknown sources: "
                    f"{sorted(unknown)}"
                )
            if rule.check_type != "declaration_evidence_presence":
                raise ValueError(
                    f"Unsupported check_type for {rule.rule_id}: "
                    f"{rule.check_type}"
                )

        return self


@dataclass(frozen=True, slots=True)
class LoadedRulePack:
    definition: RulePackDefinition
    sha256: str
    path: Path


@lru_cache
def load_rule_pack() -> LoadedRulePack:
    raw = RULE_PACK_PATH.read_bytes()
    parsed = json.loads(raw.decode("utf-8"))
    definition = RulePackDefinition.model_validate(parsed)
    return LoadedRulePack(
        definition=definition,
        sha256=hashlib.sha256(raw).hexdigest(),
        path=RULE_PACK_PATH,
    )
