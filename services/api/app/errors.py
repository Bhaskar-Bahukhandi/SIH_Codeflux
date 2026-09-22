from dataclasses import dataclass

from fastapi import status


@dataclass(slots=True)
class AppError(Exception):
    code: str
    message: str
    status_code: int = status.HTTP_400_BAD_REQUEST
    headers: dict[str, str] | None = None


def not_found(code: str, message: str) -> AppError:
    return AppError(
        code=code,
        message=message,
        status_code=status.HTTP_404_NOT_FOUND,
    )


def conflict(code: str, message: str) -> AppError:
    return AppError(
        code=code,
        message=message,
        status_code=status.HTTP_409_CONFLICT,
    )


def unauthorized(code: str, message: str) -> AppError:
    return AppError(
        code=code,
        message=message,
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
    )


def forbidden(code: str, message: str) -> AppError:
    return AppError(
        code=code,
        message=message,
        status_code=status.HTTP_403_FORBIDDEN,
    )
