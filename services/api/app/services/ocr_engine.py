from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
from typing import Protocol

import numpy as np
from fastapi import Depends
from PIL import Image

from app.core.config import Settings, get_settings
from app.errors import service_unavailable


class OcrBackendUnavailable(RuntimeError):
    pass


class OcrInferenceFailed(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OcrDetection:
    text: str
    confidence: float
    polygon: list[list[float]]


class OcrEngine(Protocol):
    name: str
    version: str
    model_version: str
    language: str
    parameters: dict

    def extract(self, image_bytes: bytes) -> list[OcrDetection]: ...


class PaddleOcrEngine:
    name = "paddleocr"

    def __init__(
        self,
        *,
        engine: str,
        language: str,
        model_version: str,
        device: str,
        min_confidence: float,
        enable_mkldnn: bool,
    ):
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise OcrBackendUnavailable(
                "PaddleOCR is not installed in this runtime."
            ) from exc

        try:
            self._model = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                engine=engine,
                lang=language,
                ocr_version=model_version,
                device=device,
                enable_mkldnn=enable_mkldnn,
            )
        except Exception as exc:
            raise OcrBackendUnavailable(
                "PaddleOCR could not initialize with the configured runtime."
            ) from exc

        try:
            package_version = version("paddleocr")
        except PackageNotFoundError:
            package_version = "unknown"

        self.version = package_version
        self.model_version = model_version
        self.language = language
        self._min_confidence = min_confidence
        self.parameters = {
            "engine": engine,
            "device": device,
            "text_rec_score_thresh": min_confidence,
            "enable_mkldnn": enable_mkldnn,
            "document_orientation": False,
            "document_unwarping": False,
            "textline_orientation": False,
        }

    def extract(self, image_bytes: bytes) -> list[OcrDetection]:
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)

            results = list(
                self._model.predict(
                    rgb,
                    text_rec_score_thresh=self._min_confidence,
                )
            )
        except Exception as exc:
            raise OcrInferenceFailed(
                "PaddleOCR inference failed: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        detections: list[OcrDetection] = []
        for result in results:
            payload = getattr(result, "json", None)
            if callable(payload):
                payload = payload()
            if not isinstance(payload, dict):
                raise OcrInferenceFailed(
                    "PaddleOCR returned an unsupported result structure."
                )

            result_data = payload.get("res", payload)
            texts = result_data.get("rec_texts")
            scores = result_data.get("rec_scores")
            polygons = result_data.get("rec_polys")

            if texts is None or scores is None or polygons is None:
                raise OcrInferenceFailed(
                    "PaddleOCR result is missing recognition fields."
                )

            count = min(len(texts), len(scores), len(polygons))
            for index in range(count):
                text = str(texts[index]).strip()
                if not text:
                    continue

                confidence = float(scores[index])
                if not np.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
                    raise OcrInferenceFailed(
                        "PaddleOCR returned an invalid recognition score."
                    )

                polygon_array = np.asarray(polygons[index], dtype=float)
                if (
                    polygon_array.shape != (4, 2)
                    or not np.isfinite(polygon_array).all()
                ):
                    raise OcrInferenceFailed(
                        "PaddleOCR returned an invalid text polygon."
                    )

                detections.append(
                    OcrDetection(
                        text=text,
                        confidence=confidence,
                        polygon=[
                            [
                                round(float(point[0]), 3),
                                round(float(point[1]), 3),
                            ]
                            for point in polygon_array
                        ],
                    )
                )

        return detections


@lru_cache(maxsize=8)
def _cached_paddle_engine(
    engine: str,
    language: str,
    model_version: str,
    device: str,
    min_confidence: float,
    enable_mkldnn: bool,
) -> PaddleOcrEngine:
    return PaddleOcrEngine(
        engine=engine,
        language=language,
        model_version=model_version,
        device=device,
        min_confidence=min_confidence,
        enable_mkldnn=enable_mkldnn,
    )


def build_ocr_engine(settings: Settings) -> OcrEngine:
    return _cached_paddle_engine(
        settings.ocr_inference_engine,
        settings.ocr_language,
        settings.ocr_model_version,
        settings.ocr_device,
        settings.ocr_min_confidence,
        settings.ocr_enable_mkldnn,
    )


def get_ocr_engine(
    settings: Settings = Depends(get_settings),
) -> OcrEngine:
    try:
        return build_ocr_engine(settings)
    except OcrBackendUnavailable:
        raise service_unavailable(
            "ocr_backend_unavailable",
            "OCR runtime is not available on this server.",
        )
