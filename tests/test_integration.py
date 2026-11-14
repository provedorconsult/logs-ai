"""Run against a dedicated disposable PostgreSQL database, never production."""

import os

import psycopg
import pytest
from database_guard import connect_test_database, validate_test_database
from fastapi.testclient import TestClient

from logs_ai.main import app
from logs_ai.migrate import migrate

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="Set TEST_DATABASE_URL to a disposable database"
)


@pytest.fixture(autouse=True)
def database(monkeypatch):
    url = os.environ["TEST_DATABASE_URL"]
    validate_test_database(url)
    monkeypatch.setenv("DATABASE_URL", url)
    with connect_test_database(url) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
    yield
    with connect_test_database(url) as conn:
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


def test_mikrotik_event_is_committed_without_raw_password_or_schema_change():
    from logs_ai.collector import store
    from logs_ai.mikrotik import normalize

    migrate()
    event = normalize(
        b"system,info ppp secret synthetic-user changed by test-admin (password=do-not-store)"
    )
    store(event, "192.168.15.1")
    with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as conn:
        source, message, attributes = conn.execute(
            "SELECT source,message,attributes FROM log_events"
        ).fetchone()
        assert source == "mikrotik:192.168.15.1"
        assert message == "ppp.user.updated"
        assert attributes["username"] == "synthetic-user"
        assert attributes["actor"] == "test-admin"
        assert "do-not-store" not in str(attributes)
        assert conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 1


def test_mikrotik_tcp_to_real_postgresql_pipeline():
    import asyncio

    from logs_ai.collector import Receiver

    migrate()

    async def scenario():
        receiver = Receiver("127.0.0.1")
        worker = asyncio.create_task(receiver.consume())
        server = await asyncio.start_server(receiver.handle, "127.0.0.1", 0)
        _, writer = await asyncio.open_connection("127.0.0.1", server.sockets[0].getsockname()[1])
        frames = [
            (
                b"CEF:0|MikroTik|RouterOS|7.24.5|ppp,info|"
                b"logs-ai-ppp: <pppoe-synthetic>: authenticated|6|"
            ),
            b"ppp,info logs-ai-ppp: synthetic logged out, 60 1000 2000",
            (
                b"system,info logs-ai-admin: ppp secret synthetic changed by test-admin "
                b"(password=do-not-store)"
            ),
            b"system,info logs-ai-admin: user operator added by test-admin",
        ]
        writer.write(b"\n".join(frames) + b"\n")
        await writer.drain()
        for _ in range(100):
            if receiver.stats["received"] == 4:
                break
            await asyncio.sleep(0.01)
        await asyncio.wait_for(receiver.queue.join(), timeout=10)
        assert receiver.stats["persisted"] == 4
        writer.close()
        await writer.wait_closed()
        server.close()
        await server.wait_closed()
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)

    asyncio.run(scenario())
    with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as conn:
        rows = conn.execute("SELECT attributes FROM log_events ORDER BY id").fetchall()
        assert [r[0]["event_kind"] for r in rows] == [
            "pppoe.authenticated",
            "pppoe.session.ended",
            "ppp.user.updated",
            "routeros.admin_user.created",
        ]
        assert "do-not-store" not in str(rows)
