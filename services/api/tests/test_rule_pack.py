from datetime import date

from app.models.declaration import DeclarationType
from app.services.rule_pack import load_rule_pack


def test_rule_pack_is_versioned_hashed_and_source_linked():
    load_rule_pack.cache_clear()
    loaded = load_rule_pack()

    assert loaded.definition.rule_pack_id == "lmpc-retail-evidence"
    assert loaded.definition.version == "2026.09-v1"
    assert loaded.definition.verified_on == date(2026, 9, 23)
    assert len(loaded.sha256) == 64

    rules = {rule.rule_id: rule for rule in loaded.definition.rules}
    assert set(rules) == {
        "LMPC-R6-1-C-NET-QUANTITY-EVIDENCE",
        "LMPC-R6-1-E-MRP-EVIDENCE",
    }

    net_quantity = rules["LMPC-R6-1-C-NET-QUANTITY-EVIDENCE"]
    assert net_quantity.declaration_type is DeclarationType.NET_QUANTITY
    assert net_quantity.effective_from == date(2011, 4, 1)
    assert net_quantity.applicability_note

    mrp = rules["LMPC-R6-1-E-MRP-EVIDENCE"]
    assert mrp.declaration_type is DeclarationType.MRP
    assert mrp.effective_from == date(2022, 10, 1)
    assert mrp.applicability_note

    known_sources = {
        source.source_id
        for source in loaded.definition.sources
    }
    for rule in loaded.definition.rules:
        assert set(rule.source_ids) <= known_sources
