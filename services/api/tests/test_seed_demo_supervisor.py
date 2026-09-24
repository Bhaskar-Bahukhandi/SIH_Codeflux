from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cli.seed_demo_supervisor import provision_demo_supervisor
from app.models.user import User, UserRole
from app.security import verify_password


def test_provisions_new_demo_supervisor(db_session: Session) -> None:
    user, created = provision_demo_supervisor(
        db_session,
        email="Supervisor@Codeflux.Demo",
        password="Codeflux@SIH2026!",
    )

    assert created is True
    assert user.email == "supervisor@codeflux.demo"
    assert user.role is UserRole.SUPERVISOR
    assert user.is_active is True
    assert verify_password("Codeflux@SIH2026!", user.password_hash)


def test_reuses_same_email_and_promotes_existing_user(
    db_session: Session,
    user_factory,
) -> None:
    existing = user_factory(
        UserRole.OFFICER,
        email="supervisor@codeflux.demo",
        password="OldPassword123!",
        active=False,
    )

    user, created = provision_demo_supervisor(
        db_session,
        email="supervisor@codeflux.demo",
        password="Codeflux@SIH2026!",
        full_name="CODEFLUX Demo Supervisor",
    )

    assert created is False
    assert user.id == existing.id
    assert user.role is UserRole.SUPERVISOR
    assert user.full_name == "CODEFLUX Demo Supervisor"
    assert user.is_active is True
    assert verify_password("Codeflux@SIH2026!", user.password_hash)
    assert not verify_password("OldPassword123!", user.password_hash)

    users = list(db_session.scalars(select(User)).all())
    assert len(users) == 1
