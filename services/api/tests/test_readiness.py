from sqlalchemy.exc import SQLAlchemyError

from app.db import get_db


def test_database_readiness_uses_database(client):
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_database_readiness_hides_internal_error(client):
    def broken_db():
        class BrokenSession:
            def execute(self, _):
                raise SQLAlchemyError("sensitive database detail")

        yield BrokenSession()

    client.app.dependency_overrides[get_db] = broken_db

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "database_unavailable",
            "message": "Database is not ready.",
        }
    }
    assert "sensitive" not in response.text
