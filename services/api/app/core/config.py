from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEVELOPMENT_JWT_SECRET = "development-only-change-me-before-production"


class Settings(BaseSettings):
    app_name: str = "CODEFLUX API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://codeflux:codeflux@localhost:5432/codeflux"

    media_root: Path = Path("./local_data/media")
    dashboard_root: Path | None = None
    max_capture_mb: int = Field(default=12, ge=1, le=50)
    max_capture_pixels: int = Field(default=40_000_000, ge=1_000_000, le=100_000_000)

    quality_sharpness_retake: float = Field(default=60.0, ge=0)
    quality_sharpness_review: float = Field(default=110.0, ge=0)
    quality_brightness_retake_low: float = Field(default=40.0, ge=0, le=255)
    quality_brightness_retake_high: float = Field(default=220.0, ge=0, le=255)
    quality_brightness_review_low: float = Field(default=60.0, ge=0, le=255)
    quality_brightness_review_high: float = Field(default=200.0, ge=0, le=255)
    quality_dark_fraction_retake: float = Field(default=0.60, ge=0, le=1)
    quality_bright_fraction_retake: float = Field(default=0.60, ge=0, le=1)
    quality_glare_fraction_retake: float = Field(default=0.08, ge=0, le=1)
    quality_glare_fraction_review: float = Field(default=0.03, ge=0, le=1)
    quality_glare_intensity: int = Field(default=245, ge=0, le=255)
    quality_glare_saturation_max: int = Field(default=40, ge=0, le=255)
    quality_glare_component_max_fraction: float = Field(default=0.08, gt=0, le=1)

    geometry_min_area_ratio: float = Field(default=0.20, gt=0, lt=1)
    geometry_max_area_ratio: float = Field(default=0.95, gt=0, le=1)
    geometry_min_side_px: float = Field(default=60.0, gt=0)
    geometry_min_angle_score: float = Field(default=0.60, ge=0, le=1)
    geometry_correction_score: float = Field(default=0.78, ge=0, le=1)
    geometry_detection_max_dimension: int = Field(default=1600, ge=320, le=4096)
    geometry_canny_low: int = Field(default=60, ge=0, le=255)
    geometry_canny_high: int = Field(default=180, ge=0, le=255)
    geometry_approximation_epsilon: float = Field(default=0.02, gt=0, le=0.10)

    ocr_inference_engine: Literal["paddle", "transformers"] = "paddle"
    ocr_language: str = "en"
    ocr_model_version: str = "PP-OCRv5"
    ocr_device: str = "cpu"
    ocr_min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    ocr_detection_max_dimension: int = Field(default=960, ge=320, le=4000)
    # Correctness-first default for current PaddlePaddle 3.3.x CPU runtimes:
    # PP-OCRv5 can hit an upstream oneDNN/PIR conversion regression.
    ocr_enable_mkldnn: bool = False

    jwt_secret: str = DEVELOPMENT_JWT_SECRET
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "codeflux-api"
    jwt_access_minutes: int = Field(default=60, ge=5, le=1440)

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_postgres_driver(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value[len("postgres://"):]
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://"):]
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
    )

    @property
    def max_capture_bytes(self) -> int:
        return self.max_capture_mb * 1024 * 1024


def validate_runtime_settings(settings: Settings) -> None:
    environment = settings.app_env.strip().lower()
    if environment not in {"development", "test"}:
        if (
            settings.jwt_secret == DEVELOPMENT_JWT_SECRET
            or len(settings.jwt_secret) < 32
        ):
            raise RuntimeError(
                "JWT_SECRET must be replaced with a strong deployment secret "
                "outside development/test."
            )

    if settings.quality_sharpness_review < settings.quality_sharpness_retake:
        raise RuntimeError(
            "QUALITY_SHARPNESS_REVIEW must be >= QUALITY_SHARPNESS_RETAKE."
        )
    if not (
        settings.quality_brightness_retake_low
        <= settings.quality_brightness_review_low
        < settings.quality_brightness_review_high
        <= settings.quality_brightness_retake_high
    ):
        raise RuntimeError("Quality brightness thresholds are inconsistent.")
    if settings.quality_glare_fraction_review > settings.quality_glare_fraction_retake:
        raise RuntimeError(
            "QUALITY_GLARE_FRACTION_REVIEW must be <= "
            "QUALITY_GLARE_FRACTION_RETAKE."
        )

    if settings.geometry_min_area_ratio >= settings.geometry_max_area_ratio:
        raise RuntimeError(
            "GEOMETRY_MIN_AREA_RATIO must be lower than GEOMETRY_MAX_AREA_RATIO."
        )
    if settings.geometry_canny_low >= settings.geometry_canny_high:
        raise RuntimeError(
            "GEOMETRY_CANNY_LOW must be lower than GEOMETRY_CANNY_HIGH."
        )

    if not settings.ocr_language.strip():
        raise RuntimeError("OCR_LANGUAGE must not be blank.")
    if not settings.ocr_model_version.strip():
        raise RuntimeError("OCR_MODEL_VERSION must not be blank.")
    if not settings.ocr_device.strip():
        raise RuntimeError("OCR_DEVICE must not be blank.")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    validate_runtime_settings(settings)
    return settings
