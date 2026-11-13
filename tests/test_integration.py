"""Run against a dedicated disposable PostgreSQL database, never production."""

import os
from urllib.parse import urlsplit

import psycopg
import pytest
from fastapi.testclient import TestClient

from logs_ai.main import app
from logs_ai.migrate import migrate

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="Set TEST_DATABASE_URL to a disposable database"
)


@pytest.fixture(autouse=True)
def database(monkeypatch):
    url = os.environ["TEST_DATABASE_URL"]
    if not urlsplit(url).path.rstrip("/").endswith(("_ci", "_test")):
        pytest.fail("TEST_DATABASE_URL must target a disposable database ending in _ci or _test")
    monkeypatch.setenv("DATABASE_URL", url)
    with psycopg.connect(url) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
    yield
    with psycopg.connect(url) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")


def test_migrations_idempotence_persistence_and_health(monkeypatch):
    monkeypatch.setenv("APP_REVISION", "test-revision")
    client = TestClient(app)
    assert client.get("/health").status_code == 503
    migrate()
    migrate()
    with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as conn:
        assert conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 1
        conn.execute("INSERT INTO log_events(source, message) VALUES ('test', 'synthetic')")
    with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as conn:
        assert conn.execute("SELECT message FROM log_events").fetchone()[0] == "synthetic"
    response = client.get("/health")
    assert response.json() == {"status": "ok", "database": "ok"}
    assert response.headers["X-App-Revision"] == "test-revision"


def test_migration_failure_rolls_back(tmp_path):
    (tmp_path / "001_broken.sql").write_text("CREATE TABLE partial(id int); SELECT broken;")
    with pytest.raises(psycopg.Error):
        migrate(tmp_path)
    with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as conn:
        assert conn.execute("SELECT to_regclass('public.partial')").fetchone()[0] is None
        assert conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone()[0] is None


def test_changed_migration_is_rejected(tmp_path):
    migrate()
    (tmp_path / "001_initial.sql").write_text("SELECT 1;")
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        migrate(tmp_path)


def test_older_release_is_rejected(tmp_path):
    migrate()
    (tmp_path / "002_future.sql").write_text("SELECT 1;")
    with pytest.raises(RuntimeError, match="newer"):
        migrate(tmp_path)


def test_unreachable_database_returns_503(monkeypatch):
    migrate()
    monkeypatch.setenv("DATABASE_URL", "postgresql://invalid:invalid@127.0.0.1:1/unreachable")
    assert TestClient(app).get("/health").status_code == 503


def test_invalid_severity_is_rejected():
    migrate()
    with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("INSERT INTO log_events(source, message, severity) VALUES ('t', 't', 8)")


def test_concurrent_migrations_are_serialized():
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: migrate(), range(2)))
    with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as conn:
        assert conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 1
