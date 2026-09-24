from __future__ import annotations

import os

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models.user import User, UserRole
from app.security import hash_password


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


def main() -> None:
    email = required_env("CODEFLUX_INTEGRATION_OFFICER_EMAIL").lower()
    password = required_env("CODEFLUX_INTEGRATION_OFFICER_PASSWORD")

    with SessionLocal() as session:
        existing = session.scalar(
            select(User).where(func.lower(User.email) == email)
        )
        if existing is not None:
            if existing.role is not UserRole.OFFICER or not existing.is_active:
                raise RuntimeError(
                    "Existing integration user is not an active Officer."
                )
            print(f"Integration Officer already exists: {existing.id}")
            return

        user = User(
            full_name="Live Integration Officer",
            email=email,
            password_hash=hash_password(password),
            role=UserRole.OFFICER,
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        print(f"Created integration Officer: {user.id}")


if __name__ == "__main__":
    main()
