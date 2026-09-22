from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO
from math import sqrt

import cv2
import numpy as np
from PIL import Image

from app.core.config import Settings
from app.models.geometry import GeometryStatus

GEOMETRY_ALGORITHM_VERSION = "geometry-v1"
PERSPECTIVE_PROCESSING_VERSION = "perspective-v1"


@dataclass(frozen=True, slots=True)
class GeometryThresholds:
    min_area_ratio: float
    max_area_ratio: float
    min_side_px: float
    min_angle_score: float
    correction_score: float
    detection_max_dimension: int
    canny_low: int
    canny_high: int
    approximation_epsilon: float

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GeometryAnalysis:
    status: GeometryStatus
    corners: list[list[float]] | None
    area_ratio: float | None
    angle_score: float | None
    geometry_score: float | None
    reasons: list[str]
    corrected_jpeg: bytes | None
    corrected_width_px: int | None
    corrected_height_px: int | None


def geometry_thresholds_from_settings(settings: Settings) -> GeometryThresholds:
    return GeometryThresholds(
        min_area_ratio=settings.geometry_min_area_ratio,
        max_area_ratio=settings.geometry_max_area_ratio,
        min_side_px=settings.geometry_min_side_px,
        min_angle_score=settings.geometry_min_angle_score,
        correction_score=settings.geometry_correction_score,
        detection_max_dimension=settings.geometry_detection_max_dimension,
        canny_low=settings.geometry_canny_low,
        canny_high=settings.geometry_canny_high,
        approximation_epsilon=settings.geometry_approximation_epsilon,
    )


def _order_points(points: np.ndarray) -> np.ndarray:
    points = points.astype(np.float32)
    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1).reshape(-1)

    top_left = points[np.argmin(sums)]
    bottom_right = points[np.argmax(sums)]
    top_right = points[np.argmin(diffs)]
    bottom_left = points[np.argmax(diffs)]
    return np.array(
        [top_left, top_right, bottom_right, bottom_left],
        dtype=np.float32,
    )


def _side_lengths(ordered: np.ndarray) -> list[float]:
    return [
        float(np.linalg.norm(ordered[1] - ordered[0])),
        float(np.linalg.norm(ordered[2] - ordered[1])),
        float(np.linalg.norm(ordered[3] - ordered[2])),
        float(np.linalg.norm(ordered[0] - ordered[3])),
    ]


def _angle_score(ordered: np.ndarray) -> float:
    scores: list[float] = []
    for index in range(4):
        previous = ordered[(index - 1) % 4] - ordered[index]
        following = ordered[(index + 1) % 4] - ordered[index]
        denominator = float(np.linalg.norm(previous) * np.linalg.norm(following))
        if denominator <= 1e-6:
            return 0.0
        cosine = abs(float(np.dot(previous, following)) / denominator)
        scores.append(max(0.0, 1.0 - min(1.0, cosine)))
    return float(sum(scores) / len(scores))


def _warp_perspective(
    rgb: np.ndarray,
    ordered: np.ndarray,
) -> tuple[bytes, int, int] | None:
    top, right, bottom, left = _side_lengths(ordered)
    width = int(round(max(top, bottom)))
    height = int(round(max(left, right)))

    if width < 2 or height < 2:
        return None

    destination = np.array(
        [
            [0.0, 0.0],
            [width - 1.0, 0.0],
            [width - 1.0, height - 1.0],
            [0.0, height - 1.0],
        ],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(ordered, destination)
    corrected = cv2.warpPerspective(
        rgb,
        transform,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )

    bgr = cv2.cvtColor(corrected, cv2.COLOR_RGB2BGR)
    success, encoded = cv2.imencode(
        ".jpg",
        bgr,
        [int(cv2.IMWRITE_JPEG_QUALITY), 94],
    )
    if not success:
        return None
    return encoded.tobytes(), width, height


def analyze_perspective(
    normalized_jpeg: bytes,
    *,
    thresholds: GeometryThresholds,
) -> GeometryAnalysis:
    with Image.open(BytesIO(normalized_jpeg)) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)

    height, width = rgb.shape[:2]
    if width < 2 or height < 2:
        return GeometryAnalysis(
            status=GeometryStatus.NOT_DETECTED,
            corners=None,
            area_ratio=None,
            angle_score=None,
            geometry_score=None,
            reasons=["invalid_image_dimensions"],
            corrected_jpeg=None,
            corrected_width_px=None,
            corrected_height_px=None,
        )

    max_dimension = max(width, height)
    scale = 1.0
    detection_rgb = rgb
    if max_dimension > thresholds.detection_max_dimension:
        scale = thresholds.detection_max_dimension / max_dimension
        detection_rgb = cv2.resize(
            rgb,
            (
                max(2, int(round(width * scale))),
                max(2, int(round(height * scale))),
            ),
            interpolation=cv2.INTER_AREA,
        )

    gray = cv2.cvtColor(detection_rgb, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(
        blurred,
        thresholds.canny_low,
        thresholds.canny_high,
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(
        closed,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    image_area = float(detection_rgb.shape[0] * detection_rgb.shape[1])
    candidates: list[tuple[float, np.ndarray, float, float, float]] = []

    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area <= 0:
            continue

        area_ratio = area / image_area
        if (
            area_ratio < thresholds.min_area_ratio
            or area_ratio > thresholds.max_area_ratio
        ):
            continue

        perimeter = float(cv2.arcLength(contour, True))
        if perimeter <= 0:
            continue

        approximation = cv2.approxPolyDP(
            contour,
            thresholds.approximation_epsilon * perimeter,
            True,
        )
        if len(approximation) != 4 or not cv2.isContourConvex(approximation):
            continue

        detected = approximation.reshape(4, 2).astype(np.float32)
        ordered_detected = _order_points(detected)
        side_lengths = _side_lengths(ordered_detected)
        if min(side_lengths) < thresholds.min_side_px * scale:
            continue

        angle_score = _angle_score(ordered_detected)
        if angle_score < thresholds.min_angle_score:
            continue

        usable_area_span = max(
            thresholds.max_area_ratio - thresholds.min_area_ratio,
            1e-6,
        )
        area_score = min(
            1.0,
            max(
                0.0,
                (area_ratio - thresholds.min_area_ratio) / usable_area_span,
            ),
        )
        geometry_score = 0.40 * area_score + 0.60 * angle_score

        ordered_original = ordered_detected / scale
        candidates.append(
            (
                geometry_score,
                ordered_original,
                area_ratio,
                angle_score,
                area_score,
            )
        )

    if not candidates:
        return GeometryAnalysis(
            status=GeometryStatus.NOT_DETECTED,
            corners=None,
            area_ratio=None,
            angle_score=None,
            geometry_score=None,
            reasons=["no_reliable_quadrilateral"],
            corrected_jpeg=None,
            corrected_width_px=None,
            corrected_height_px=None,
        )

    candidates.sort(key=lambda item: item[0], reverse=True)
    geometry_score, ordered, area_ratio, angle_score, _ = candidates[0]

    corners = [
        [round(float(point[0]), 3), round(float(point[1]), 3)]
        for point in ordered
    ]
    geometry_score = round(float(geometry_score), 6)
    angle_score = round(float(angle_score), 6)
    area_ratio = round(float(area_ratio), 6)

    if geometry_score < thresholds.correction_score:
        return GeometryAnalysis(
            status=GeometryStatus.REVIEW_RECOMMENDED,
            corners=corners,
            area_ratio=area_ratio,
            angle_score=angle_score,
            geometry_score=geometry_score,
            reasons=["geometry_below_correction_gate"],
            corrected_jpeg=None,
            corrected_width_px=None,
            corrected_height_px=None,
        )

    warped = _warp_perspective(rgb, ordered)
    if warped is None:
        return GeometryAnalysis(
            status=GeometryStatus.REVIEW_RECOMMENDED,
            corners=corners,
            area_ratio=area_ratio,
            angle_score=angle_score,
            geometry_score=geometry_score,
            reasons=["perspective_warp_failed"],
            corrected_jpeg=None,
            corrected_width_px=None,
            corrected_height_px=None,
        )

    corrected_jpeg, corrected_width, corrected_height = warped
    return GeometryAnalysis(
        status=GeometryStatus.CORRECTION_AVAILABLE,
        corners=corners,
        area_ratio=area_ratio,
        angle_score=angle_score,
        geometry_score=geometry_score,
        reasons=[],
        corrected_jpeg=corrected_jpeg,
        corrected_width_px=corrected_width,
        corrected_height_px=corrected_height,
    )
