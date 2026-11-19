"""Offline tests for database URL selection and safe credential encoding."""

from sqlalchemy.engine import make_url

from app.core.config import Settings


def make_settings(**values):
    values.setdefault("DATABASE_URL", None)
    return Settings(_env_file=None, **values)


def test_sqlite_database_url_is_preserved():
    settings = make_settings(DATABASE_URL="sqlite:///:memory:")

    assert settings.sqlalchemy_database_uri == "sqlite:///:memory:"


def test_mysql_component_settings_build_pymysql_url():
    settings = make_settings(
        DB_HOST="mysql.example.test",
        DB_PORT=3307,
        DB_NAME="wastewise_test",
        DB_USER="app_user",
        DB_PASSWORD="safe-placeholder",
    )
    url = make_url(settings.sqlalchemy_database_uri)

    assert url.drivername == "mysql+pymysql"
    assert url.host == "mysql.example.test"
    assert url.port == 3307
    assert url.database == "wastewise_test"
    assert url.username == "app_user"
    assert url.password == "safe-placeholder"


def test_neon_postgresql_url_is_normalized_to_psycopg_and_ssl_preserved():
    settings = make_settings(
        DATABASE_URL=(
            "postgresql://neon_user:p%40ss%3Aword@ep-example-pooler.ap-southeast-1.aws.neon.tech"
            ":5432/wastewise_db?sslmode=require"
        )
    )
    url = make_url(settings.sqlalchemy_database_uri)

    assert url.drivername == "postgresql+psycopg"
    assert url.username == "neon_user"
    assert url.password == "p@ss:word"
    assert url.host == "ep-example-pooler.ap-southeast-1.aws.neon.tech"
    assert url.database == "wastewise_db"
    assert url.query["sslmode"] == "require"


def test_mysql_credentials_with_reserved_url_characters_round_trip():
    settings = make_settings(
        DB_USER="app@service",
        DB_PASSWORD="p@ss:/?#%word",
    )
    url = make_url(settings.sqlalchemy_database_uri)

    assert url.username == "app@service"
    assert url.password == "p@ss:/?#%word"


def test_explicit_database_url_takes_precedence_over_mysql_settings():
    settings = make_settings(
        DATABASE_URL="sqlite:///:memory:",
        DB_HOST="mysql.example.test",
        DB_PASSWORD="ignored-placeholder",
    )

    assert settings.sqlalchemy_database_uri == "sqlite:///:memory:"
