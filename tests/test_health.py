from contextlib import contextmanager

from fastapi.testclient import TestClient

from logs_ai import main

client = TestClient(main.app)


def test_database_failure_is_unavailable_and_redacted(monkeypatch):
    def fail():
        raise RuntimeError("postgres://user:secret@private/db")

    monkeypatch.setattr(main, "connect", fail)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
    assert "secret" not in response.text


def test_missing_schema_is_unavailable(monkeypatch):
    class Connection:
        def execute(self, *args):
            return self

        def fetchone(self):
            return (False,)

    @contextmanager
    def connect():
        yield Connection()

    monkeypatch.setattr(main, "connect", connect)
    assert client.get("/health").status_code == 503
