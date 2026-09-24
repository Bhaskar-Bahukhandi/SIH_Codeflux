from __future__ import annotations

import os

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.user import User, UserRole
from app.security import hash_password


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


def provision_demo_supervisor(
    session: Session,
    *,
    email: str,
    password: str,
    full_name: str = "CODEFLUX Demo Supervisor",
) -> tuple[User, bool]:
    normalized_email = email.strip().lower()
    existing = session.scalar(
        select(User).where(func.lower(User.email) == normalized_email)
    )

    created = existing is None
    user = existing or User(email=normalized_email)

    user.full_name = full_name
    user.email = normalized_email
    user.password_hash = hash_password(password)
    user.role = UserRole.SUPERVISOR
    user.is_active = True

    if created:
        session.add(user)

    session.commit()
    session.refresh(user)
    return user, created


def main() -> None:
    email = required_env("CODEFLUX_DEMO_SUPERVISOR_EMAIL")
    password = required_env("CODEFLUX_DEMO_SUPERVISOR_PASSWORD")
    full_name = (
        os.environ.get("CODEFLUX_DEMO_SUPERVISOR_NAME", "").strip()
        or "CODEFLUX Demo Supervisor"
    )

    with SessionLocal() as session:
        user, created = provision_demo_supervisor(
            session,
            email=email,
            password=password,
            full_name=full_name,
        )
        action = "Created" if created else "Updated"
        print(
            f"{action} active demo Supervisor: "
            f"{user.email} ({user.id})"
        )


if __name__ == "__main__":
    main()
