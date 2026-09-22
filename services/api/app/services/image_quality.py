from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps

from app.core.config import Settings
from app.models.quality import CaptureQualityStatus

PREPROCESSING_VERSION = "normalize-v1"
QUALITY_ALGORITHM_VERSION = "quality-v1"


@dataclass(frozen=True, slots=True)
class QualityThresholds:
    sharpness_retake: float
    sharpness_review: float
    brightness_retake_low: float
    brightness_retake_high: float
    brightness_review_low: float
    brightness_review_high: float
    dark_fraction_retake: float
    bright_fraction_retake: float
    glare_fraction_retake: float
    glare_fraction_review: float
    glare_intensity: int
    glare_saturation_max: int
    glare_component_max_fraction: float

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class NormalizedImage:
    data: bytes
    width_px: int
    height_px: int
    mime_type: str = "image/jpeg"
    extension: str = ".jpg"


@dataclass(frozen=True, slots=True)
class QualityResult:
    status: CaptureQualityStatus
    sharpness_score: float
    brightness_mean: float
    dark_fraction: float
    bright_fraction: float
    glare_fraction: float
    reasons: list[str]


def quality_thresholds_from_settings(settings: Settings) -> QualityThresholds:
    return QualityThresholds(
        sharpness_retake=settings.quality_sharpness_retake,
        sharpness_review=settings.quality_sharpness_review,
        brightness_retake_low=settings.quality_brightness_retake_low,
        brightness_retake_high=settings.quality_brightness_retake_high,
        brightness_review_low=settings.quality_brightness_review_low,
        brightness_review_high=settings.quality_brightness_review_high,
        dark_fraction_retake=settings.quality_dark_fraction_retake,
        bright_fraction_retake=settings.quality_bright_fraction_retake,
        glare_fraction_retake=settings.quality_glare_fraction_retake,
        glare_fraction_review=settings.quality_glare_fraction_review,
        glare_intensity=settings.quality_glare_intensity,
        glare_saturation_max=settings.quality_glare_saturation_max,
        glare_component_max_fraction=settings.quality_glare_component_max_fraction,
    )


def normalize_capture(data: bytes) -> NormalizedImage:
    with Image.open(BytesIO(data)) as source:
        oriented = ImageOps.exif_transpose(source)
        if oriented.mode in {"RGBA", "LA"}:
            background = Image.new("RGB", oriented.size, "white")
            alpha = oriented.getchannel("A")
            background.paste(oriented.convert("RGB"), mask=alpha)
            rgb = background
        else:
            rgb = oriented.convert("RGB")

        output = BytesIO()
        rgb.save(
            output,
            format="JPEG",
            quality=92,
            optimize=True,
            subsampling=0,
        )
        return NormalizedImage(
            data=output.getvalue(),
            width_px=rgb.width,
            height_px=rgb.height,
        )


def _glare_fraction(
    gray: np.ndarray,
    hsv: np.ndarray,
    *,
    intensity_threshold: int,
    saturation_max: int,
    component_max_fraction: float,
) -> float:
    saturation = hsv[:, :, 1]
    candidate = (
        (gray >= intensity_threshold)
        & (saturation <= saturation_max)
    ).astype(np.uint8)

    if not np.any(candidate):
        return 0.0

    total_pixels = candidate.size
    max_component_area = max(1, int(total_pixels * component_max_fraction))

    components, _, stats, _ = cv2.connectedComponentsWithStats(
        candidate,
        connectivity=8,
    )
    glare_pixels = 0
    for label in range(1, components):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if 2 <= area <= max_component_area:
            glare_pixels += area

    return glare_pixels / total_pixels


def assess_quality(
    normalized_jpeg: bytes,
    *,
    thresholds: QualityThresholds,
) -> QualityResult:
    with Image.open(BytesIO(normalized_jpeg)) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)

    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    dark_fraction = float(np.mean(gray <= 35))
    bright_fraction = float(np.mean(gray >= 245))
    glare_fraction = float(
        _glare_fraction(
            gray,
            hsv,
            intensity_threshold=thresholds.glare_intensity,
            saturation_max=thresholds.glare_saturation_max,
            component_max_fraction=thresholds.glare_component_max_fraction,
        )
    )

    retake_reasons: list[str] = []
    review_reasons: list[str] = []

    if sharpness < thresholds.sharpness_retake:
        retake_reasons.append("low_sharpness")
    elif sharpness < thresholds.sharpness_review:
        review_reasons.append("borderline_sharpness")

    if (
        brightness < thresholds.brightness_retake_low
        or dark_fraction >= thresholds.dark_fraction_retake
    ):
        retake_reasons.append("underexposed")
    elif brightness < thresholds.brightness_review_low:
        review_reasons.append("low_brightness")

    if (
        brightness > thresholds.brightness_retake_high
        or bright_fraction >= thresholds.bright_fraction_retake
    ):
        retake_reasons.append("overexposed")
    elif brightness > thresholds.brightness_review_high:
        review_reasons.append("high_brightness")

    if glare_fraction >= thresholds.glare_fraction_retake:
        retake_reasons.append("glare_risk")
    elif glare_fraction >= thresholds.glare_fraction_review:
        review_reasons.append("possible_glare")

    reasons = list(dict.fromkeys(retake_reasons + review_reasons))
    if retake_reasons:
        status = CaptureQualityStatus.RETAKE_RECOMMENDED
    elif review_reasons:
        status = CaptureQualityStatus.REVIEW_RECOMMENDED
    else:
        status = CaptureQualityStatus.PASS

    return QualityResult(
        status=status,
        sharpness_score=round(sharpness, 4),
        brightness_mean=round(brightness, 4),
        dark_fraction=round(dark_fraction, 6),
        bright_fraction=round(bright_fraction, 6),
        glare_fraction=round(glare_fraction, 6),
        reasons=reasons,
    )
