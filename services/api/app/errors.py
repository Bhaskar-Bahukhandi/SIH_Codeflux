from dataclasses import dataclass

from fastapi import status


@dataclass(slots=True)
class AppError(Exception):
    code: str
    message: str
    status_code: int = status.HTTP_400_BAD_REQUEST
    headers: dict[str, str] | None = None


def not_found(code: str, message: str) -> AppError:
    return AppError(code, message, status.HTTP_404_NOT_FOUND)


def conflict(code: str, message: str) -> AppError:
    return AppError(code, message, status.HTTP_409_CONFLICT)


def unauthorized(code: str, message: str) -> AppError:
    return AppError(
        code,
        message,
        status.HTTP_401_UNAUTHORIZED,
        {"WWW-Authenticate": "Bearer"},
    )


def forbidden(code: str, message: str) -> AppError:
    return AppError(code, message, status.HTTP_403_FORBIDDEN)


def payload_too_large(code: str, message: str) -> AppError:
    return AppError(code, message, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)


def unsupported_media(code: str, message: str) -> AppError:
    return AppError(code, message, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)


def unprocessable(code: str, message: str) -> AppError:
    return AppError(code, message, status.HTTP_422_UNPROCESSABLE_ENTITY)


def service_unavailable(code: str, message: str) -> AppError:
    return AppError(code, message, status.HTTP_503_SERVICE_UNAVAILABLE)
