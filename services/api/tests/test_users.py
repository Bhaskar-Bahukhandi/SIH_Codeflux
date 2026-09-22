from app.models.user import User, UserRole


def test_user_role_foundation_persists(db_session):
    user = User(
        full_name="Demo Officer",
        email="officer@example.test",
        role=UserRole.OFFICER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id
    assert user.role is UserRole.OFFICER
    assert user.is_active is True
