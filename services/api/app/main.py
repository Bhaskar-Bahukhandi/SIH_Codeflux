from fastapi import FastAPI

from app.api.inspections import router as inspections_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
    )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(inspections_router, prefix=settings.api_prefix)
    return app


app = create_app()
