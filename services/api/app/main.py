from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.captures import router as captures_router
from app.api.declarations import router as declarations_router
from app.api.finalizations import router as finalizations_router
from app.api.geometry import router as geometry_router
from app.api.inspections import router as inspections_router
from app.api.ocr import router as ocr_router
from app.api.officer_reviews import router as officer_reviews_router
from app.api.quality import router as quality_router
from app.api.rule_evaluations import router as rule_evaluations_router
from app.api.system import router as system_router
from app.core.config import get_settings
from app.errors import AppError


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
    )

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    app.include_router(system_router)
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(inspections_router, prefix=settings.api_prefix)
    app.include_router(captures_router, prefix=settings.api_prefix)
    app.include_router(quality_router, prefix=settings.api_prefix)
    app.include_router(geometry_router, prefix=settings.api_prefix)
    app.include_router(ocr_router, prefix=settings.api_prefix)
    app.include_router(officer_reviews_router, prefix=settings.api_prefix)
    app.include_router(declarations_router, prefix=settings.api_prefix)
    app.include_router(rule_evaluations_router, prefix=settings.api_prefix)
    app.include_router(finalizations_router, prefix=settings.api_prefix)

    if settings.dashboard_root is not None:
        dashboard_root = settings.dashboard_root.expanduser().resolve()
        index_path = dashboard_root / "index.html"
        if not index_path.is_file():
            raise RuntimeError(
                "DASHBOARD_ROOT is configured but index.html is missing: "
                f"{index_path}"
            )
        app.mount(
            "/",
            StaticFiles(directory=dashboard_root, html=True),
            name="dashboard",
        )

    return app


app = create_app()
