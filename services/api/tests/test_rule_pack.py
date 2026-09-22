from app.models.declaration import DeclarationType
from app.services.rule_pack import load_rule_pack


def test_rule_pack_is_versioned_hashed_and_source_linked():
    load_rule_pack.cache_clear()
    loaded = load_rule_pack()

    assert loaded.definition.rule_pack_id == "lmpc-retail-evidence"
    assert loaded.definition.version == "2026.09-v1"
    assert len(loaded.sha256) == 64

    rules = {rule.rule_id: rule for rule in loaded.definition.rules}
    assert set(rules) == {
        "LMPC-R6-1-C-NET-QUANTITY-EVIDENCE",
        "LMPC-R6-1-E-MRP-EVIDENCE",
    }
    assert rules["LMPC-R6-1-C-NET-QUANTITY-EVIDENCE"].declaration_type is (
        DeclarationType.NET_QUANTITY
    )
    assert rules["LMPC-R6-1-E-MRP-EVIDENCE"].declaration_type is DeclarationType.MRP
