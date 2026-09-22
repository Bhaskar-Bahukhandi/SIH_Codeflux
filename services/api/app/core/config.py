from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEVELOPMENT_JWT_SECRET = "development-only-change-me-before-production"


class Settings(BaseSettings):
    app_name: str = "CODEFLUX API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://codeflux:codeflux@localhost:5432/codeflux"

    media_root: Path = Path("./local_data/media")
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

    jwt_secret: str = DEVELOPMENT_JWT_SECRET
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "codeflux-api"
    jwt_access_minutes: int = Field(default=60, ge=5, le=1440)

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


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    validate_runtime_settings(settings)
    return settings
