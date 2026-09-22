from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import create_app
from app.models.user import User, UserRole
from app.security import hash_password

DEFAULT_TEST_PASSWORD = "TestPassword123!"


@pytest.fixture
def db_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(db_session: Session) -> TestClient:
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def user_factory(db_session: Session):
    def create_user(
        role: UserRole = UserRole.OFFICER,
        *,
        email: str | None = None,
        password: str = DEFAULT_TEST_PASSWORD,
        active: bool = True,
    ) -> User:
        user = User(
            full_name=f"Demo {role.value.title()}",
            email=email or f"{uuid4().hex}@example.test",
            password_hash=hash_password(password),
            role=role,
            is_active=active,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return create_user


@pytest.fixture
def auth_headers(client: TestClient):
    def login(user: User, password: str = DEFAULT_TEST_PASSWORD) -> dict[str, str]:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return login
