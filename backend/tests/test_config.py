import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_database_url_uses_psycopg_driver() -> None:
    settings = Settings(
        database_url="postgresql://render_user:secret@db.internal:5432/daily_digest",
        postgres_user=None,
        postgres_password=None,
        postgres_db=None,
    )

    assert settings.sqlalchemy_database_url.drivername == "postgresql+psycopg"
    assert settings.sqlalchemy_database_url.host == "db.internal"
    assert settings.sqlalchemy_database_url.database == "daily_digest"


def test_split_postgres_configuration_remains_supported() -> None:
    settings = Settings(
        database_url=None,
        postgres_user="daily_digest",
        postgres_password="secret",
        postgres_db="daily_digest",
        postgres_host="db",
        postgres_port=5432,
    )

    assert settings.sqlalchemy_database_url.drivername == "postgresql+psycopg"
    assert settings.sqlalchemy_database_url.username == "daily_digest"
    assert settings.sqlalchemy_database_url.host == "db"


def test_database_url_rejects_non_postgres_schemes() -> None:
    with pytest.raises(ValidationError, match="must be a PostgreSQL URL"):
        Settings(database_url="sqlite:///daily-digest.db")
