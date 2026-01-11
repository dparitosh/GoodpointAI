from core.postgres_config import is_postgres_database_url


def test_is_postgres_database_url_accepts_driver_urls():
    assert is_postgres_database_url("postgresql+psycopg://u:p@localhost:5432/db")
    assert is_postgres_database_url("postgresql://u:p@localhost:5432/db")
    assert is_postgres_database_url("postgres://u:p@localhost:5432/db")
    assert not is_postgres_database_url("sqlite:///./data/app.db")
