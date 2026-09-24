from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from app.services.ocr_engine import (
    OcrInferenceFailed,
    PaddleOcrEngine,
)


def image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (120, 80), (240, 240, 240)).save(
        buffer,
        format="JPEG",
        quality=95,
    )
    return buffer.getvalue()


class FakeResult:
    def __init__(self, payload):
        self.json = payload


class FakeModel:
    def __init__(self, payload):
        self.payload = payload
        self.last_threshold = None
        self.last_detection_limit = None
        self.last_detection_limit_type = None

    def predict(
        self,
        image,
        *,
        text_rec_score_thresh,
        text_det_limit_side_len,
        text_det_limit_type,
    ):
        assert isinstance(image, np.ndarray)
        assert image.shape == (80, 120, 3)
        self.last_threshold = text_rec_score_thresh
        self.last_detection_limit = text_det_limit_side_len
        self.last_detection_limit_type = text_det_limit_type
        return [FakeResult(self.payload)]


def make_engine(payload, *, threshold=0.25):
    engine = object.__new__(PaddleOcrEngine)
    engine._model = FakeModel(payload)
    engine._min_confidence = threshold
    engine._detection_max_dimension = 960
    return engine


def test_paddleocr_adapter_reads_documented_recognition_fields():
    payload = {
        "res": {
            "rec_texts": ["MRP Rs. 50", "Net Qty 100 g"],
            "rec_scores": np.array([0.95, 0.87], dtype=np.float32),
            "rec_polys": np.array(
                [
                    [[5, 6], [100, 6], [100, 25], [5, 25]],
                    [[7, 35], [108, 35], [108, 56], [7, 56]],
                ],
                dtype=np.int16,
            ),
        }
    }
    engine = make_engine(payload)

    detections = engine.extract(image_bytes())

    assert engine._model.last_threshold == 0.25
    assert engine._model.last_detection_limit == 960
    assert engine._model.last_detection_limit_type == "max"
    assert [item.text for item in detections] == [
        "MRP Rs. 50",
        "Net Qty 100 g",
    ]
    assert detections[0].confidence == pytest.approx(0.95)
    assert detections[1].confidence == pytest.approx(0.87)
    assert detections[0].polygon == [
        [5.0, 6.0],
        [100.0, 6.0],
        [100.0, 25.0],
        [5.0, 25.0],
    ]


def test_paddleocr_adapter_skips_blank_recognition_text():
    payload = {
        "res": {
            "rec_texts": ["  ", "MRP Rs. 50"],
            "rec_scores": [0.99, 0.91],
            "rec_polys": [
                [[0, 0], [10, 0], [10, 10], [0, 10]],
                [[5, 5], [80, 5], [80, 20], [5, 20]],
            ],
        }
    }
    engine = make_engine(payload)

    detections = engine.extract(image_bytes())

    assert len(detections) == 1
    assert detections[0].text == "MRP Rs. 50"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "res": {
                "rec_texts": ["bad-score"],
                "rec_scores": [1.5],
                "rec_polys": [[[0, 0], [10, 0], [10, 10], [0, 10]]],
            }
        },
        {
            "res": {
                "rec_texts": ["bad-poly"],
                "rec_scores": [0.9],
                "rec_polys": [[[0, 0], [10, 0], [10, 10]]],
            }
        },
    ],
)
def test_paddleocr_adapter_rejects_invalid_recognition_output(payload):
    engine = make_engine(payload)

    with pytest.raises(OcrInferenceFailed):
        engine.extract(image_bytes())


class FailingPredictModel:
    def predict(
        self,
        _image,
        *,
        text_rec_score_thresh,
        text_det_limit_side_len,
        text_det_limit_type,
    ):
        raise TypeError(
            "unsupported prediction argument at threshold "
            f"{text_rec_score_thresh}, detection limit "
            f"{text_det_limit_side_len}/{text_det_limit_type}"
        )


def test_paddleocr_adapter_preserves_inference_cause_for_diagnostics():
    engine = object.__new__(PaddleOcrEngine)
    engine._model = FailingPredictModel()
    engine._min_confidence = 0.25
    engine._detection_max_dimension = 960

    with pytest.raises(
        OcrInferenceFailed,
        match="TypeError: unsupported prediction argument",
    ):
        engine.extract(image_bytes())
