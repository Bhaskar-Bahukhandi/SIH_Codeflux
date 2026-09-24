from app.models.declaration import DeclarationFusionStatus, DeclarationType
from app.services.declaration_extractor import (
    OcrTextEvidence,
    extract_declarations,
)
from app.services.declaration_fusion import (
    FusionObservation,
    fuse_declarations,
)


def block(block_id, order, text, confidence=0.9):
    return OcrTextEvidence(
        block_id=block_id,
        order_index=order,
        text=text,
        confidence=confidence,
    )


def summary_by_type(results, declaration_type):
    return next(
        result
        for result in results
        if result.declaration_type is declaration_type
    )


def test_extracts_mrp_and_net_quantity_without_invented_confidence():
    results = extract_declarations(
        [
            block("b1", 0, "MRP: Rs. 1,299.50", 0.94),
            block("b2", 1, "Net Wt. 250 grams", 0.87),
        ]
    )

    assert len(results) == 2

    mrp = next(
        result
        for result in results
        if result.declaration_type is DeclarationType.MRP
    )
    assert mrp.normalized_value == {
        "currency": "INR",
        "amount": "1299.50",
    }
    assert mrp.block_ids == ["b1"]
    assert mrp.ocr_confidence_min == 0.94
    assert mrp.ocr_confidence_mean == 0.94
    assert mrp.extractor_method == "mrp_label_v1"

    quantity = next(
        result
        for result in results
        if result.declaration_type is DeclarationType.NET_QUANTITY
    )
    assert quantity.normalized_value == {
        "value": "250",
        "unit": "g",
    }
    assert quantity.ocr_confidence_min == 0.87


def test_adjacent_label_and_value_blocks_keep_both_evidence_ids():
    results = extract_declarations(
        [
            block("label", 0, "MRP", 0.92),
            block("value", 1, "Rs. 50.00", 0.84),
        ]
    )

    mrp = next(
        result
        for result in results
        if result.declaration_type is DeclarationType.MRP
    )
    assert mrp.normalized_value["amount"] == "50.00"
    assert mrp.block_ids == ["label", "value"]
    assert mrp.ocr_confidence_min == 0.84
    assert mrp.ocr_confidence_mean == 0.88


def test_unlabeled_numbers_are_not_guessed_as_declarations():
    results = extract_declarations(
        [
            block("b1", 0, "50.00"),
            block("b2", 1, "100 g"),
            block("b3", 2, "Crunchy snack"),
        ]
    )

    assert results == []


def test_fusion_requires_distinct_captures_for_consistent_status():
    value = {"currency": "INR", "amount": "50.00"}

    same_capture = fuse_declarations(
        [
            FusionObservation(DeclarationType.MRP, "cap-1", value),
            FusionObservation(DeclarationType.MRP, "cap-1", value),
        ]
    )
    mrp = summary_by_type(same_capture, DeclarationType.MRP)
    assert mrp.status is DeclarationFusionStatus.SINGLE_SOURCE
    assert mrp.capture_count == 1

    two_captures = fuse_declarations(
        [
            FusionObservation(DeclarationType.MRP, "cap-1", value),
            FusionObservation(DeclarationType.MRP, "cap-2", value),
        ]
    )
    mrp = summary_by_type(two_captures, DeclarationType.MRP)
    assert mrp.status is DeclarationFusionStatus.CONSISTENT
    assert mrp.capture_count == 2
    assert mrp.canonical_value == value


def test_fusion_preserves_conflicts_and_not_detected_state():
    results = fuse_declarations(
        [
            FusionObservation(
                DeclarationType.MRP,
                "cap-1",
                {"currency": "INR", "amount": "50.00"},
            ),
            FusionObservation(
                DeclarationType.MRP,
                "cap-2",
                {"currency": "INR", "amount": "60.00"},
            ),
        ]
    )

    mrp = summary_by_type(results, DeclarationType.MRP)
    quantity = summary_by_type(results, DeclarationType.NET_QUANTITY)

    assert mrp.status is DeclarationFusionStatus.CONFLICT
    assert mrp.canonical_value is None
    assert mrp.capture_count == 2
    assert len(mrp.candidate_values) == 2

    assert quantity.status is DeclarationFusionStatus.NOT_DETECTED
    assert quantity.canonical_value is None
    assert quantity.candidate_values == []
    assert quantity.observation_count == 0


def test_additive_promotional_net_quantity_uses_explicit_total():
    results = extract_declarations(
        [
            block("label", 0, "BISCUITS NET WEIGHT", 0.98),
            block("value", 1, "40g+10g EXTRA# = 50g", 0.97),
        ]
    )

    quantity = next(
        result
        for result in results
        if result.declaration_type is DeclarationType.NET_QUANTITY
    )
    assert quantity.normalized_value == {
        "value": "50",
        "unit": "g",
    }
    assert quantity.block_ids == ["label", "value"]
    assert quantity.extractor_method == "net_quantity_additive_total_v1"


def test_additive_total_requires_same_unit_and_consistent_arithmetic():
    results = extract_declarations(
        [
            block("b1", 0, "NET WEIGHT 40g+10g EXTRA = 55g", 0.95),
        ]
    )

    quantity = next(
        result
        for result in results
        if result.declaration_type is DeclarationType.NET_QUANTITY
    )
    assert quantity.normalized_value == {
        "value": "40",
        "unit": "g",
    }
    assert quantity.extractor_method == "net_quantity_label_v1"
