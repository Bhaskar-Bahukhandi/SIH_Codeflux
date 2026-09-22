from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEVELOPMENT_JWT_SECRET = "development-only-change-me-before-production"


class Settings(BaseSettings):
    app_name: str = "CODEFLUX API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://codeflux:codeflux@localhost:5432/codeflux"

    jwt_secret: str = DEVELOPMENT_JWT_SECRET
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "codeflux-api"
    jwt_access_minutes: int = Field(default=60, ge=5, le=1440)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
    )


def validate_runtime_settings(settings: Settings) -> None:
    environment = settings.app_env.strip().lower()
    if environment in {"development", "test"}:
        return

    if (
        settings.jwt_secret == DEVELOPMENT_JWT_SECRET
        or len(settings.jwt_secret) < 32
    ):
        raise RuntimeError(
            "JWT_SECRET must be replaced with a strong deployment secret "
            "outside development/test."
        )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    validate_runtime_settings(settings)
    return settings
