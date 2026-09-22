from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db import get_db
from app.errors import forbidden, unauthorized
from app.models.user import User, UserRole
from app.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized("authentication_required", "Authentication is required.")

    try:
        payload = decode_access_token(credentials.credentials, settings)
    except ValueError:
        raise unauthorized("invalid_token", "The access token is invalid or expired.")

    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise unauthorized("invalid_token", "The access token is invalid or expired.")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized("invalid_token", "The access token is invalid or expired.")

    return user


def require_officer(user: User = Depends(get_current_user)) -> User:
    if user.role is not UserRole.OFFICER:
        raise forbidden(
            "officer_role_required",
            "This action is restricted to enforcement officers.",
        )
    return user
