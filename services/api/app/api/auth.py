from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.core.config import Settings, get_settings
from app.db import get_db
from app.errors import unauthorized
from app.models.user import User
from app.schemas.auth import AccessTokenResponse, CurrentUserRead, LoginRequest
from app.security import create_access_token, verify_password_or_dummy

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=AccessTokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AccessTokenResponse:
    statement = select(User).where(func.lower(User.email) == payload.email)
    user = db.scalar(statement)

    credential_hash = (
        user.password_hash
        if user is not None and user.is_active
        else None
    )
    password_valid = verify_password_or_dummy(
        payload.password,
        credential_hash,
    )

    if user is None or not user.is_active or not password_valid:
        raise unauthorized("invalid_credentials", "Invalid email or password.")

    token = create_access_token(user, settings)
    return AccessTokenResponse(
        access_token=token,
        expires_in=settings.jwt_access_minutes * 60,
    )


@router.get("/me", response_model=CurrentUserRead)
def current_user(user: User = Depends(get_current_user)) -> User:
    return user
