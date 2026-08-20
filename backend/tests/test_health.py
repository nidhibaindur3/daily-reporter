from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.main import app


class HealthySession:
    def execute(self, statement: object) -> None:
        del statement


class UnhealthySession:
    def execute(self, statement: object) -> None:
        del statement
        raise SQLAlchemyError("database unavailable")


def override_database(session: object) -> None:
    def dependency() -> Generator[object, None, None]:
        yield session

    app.dependency_overrides[get_db] = dependency


def test_health_check_returns_ok_when_database_is_available() -> None:
    override_database(HealthySession())

    try:
        response = TestClient(app).get("/api/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_check_returns_503_when_database_is_unavailable() -> None:
    override_database(UnhealthySession())

    try:
        response = TestClient(app).get("/api/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
