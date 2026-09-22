from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.inspections import router as inspections_router
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
    return app


app = create_app()
