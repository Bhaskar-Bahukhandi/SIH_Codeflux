import pytest

from app.core.config import Settings, validate_runtime_settings
from app.models.user import UserRole


def test_login_and_current_user(client, user_factory):
    user = user_factory(
        UserRole.OFFICER,
        email="officer@example.test",
    )

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "OFFICER@example.test",
            "password": "TestPassword123!",
        },
    )

    assert login.status_code == 200
    payload = login.json()
    assert payload["token_type"] == "bearer"
    assert payload["expires_in"] > 0
    assert payload["access_token"]

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )

    assert me.status_code == 200
    current = me.json()
    assert current["id"] == user.id
    assert current["email"] == "officer@example.test"
    assert current["role"] == "officer"
    assert current["is_active"] is True


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("missing@example.test", "TestPassword123!"),
        ("officer@example.test", "WrongPassword123!"),
    ],
)
def test_invalid_credentials_use_same_error(
    client,
    user_factory,
    email,
    password,
):
    user_factory(UserRole.OFFICER, email="officer@example.test")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "invalid_credentials",
            "message": "Invalid email or password.",
        }
    }


def test_inactive_user_cannot_login(client, user_factory):
    user_factory(
        UserRole.OFFICER,
        email="inactive@example.test",
        active=False,
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "inactive@example.test",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_invalid_bearer_token_is_rejected(client):
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_non_development_environment_rejects_weak_jwt_secret():
    settings = Settings(
        _env_file=None,
        app_env="production",
        jwt_secret="too-short",
    )

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validate_runtime_settings(settings)
