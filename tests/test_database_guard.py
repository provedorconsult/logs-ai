import socket
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.helpers import database_guard
from tests.helpers.database_guard import connect_test_database, validate_test_database


@pytest.fixture(autouse=True)
def opt_in(monkeypatch):
    monkeypatch.setenv("TEST_DATABASE_DISPOSABLE", "true")
    monkeypatch.setenv("TEST_DATABASE_EXPECTED_PORT", "15432")


def test_explicit_local_disposable_database_is_allowed():
    validate_test_database("postgresql://logs_ai:synthetic@127.0.0.1:15432/logs_ai_ci")


def test_disposable_opt_in_is_mandatory(monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_DISPOSABLE")
    with pytest.raises(ValueError):
        validate_test_database("postgresql://logs_ai:synthetic@127.0.0.1:15432/logs_ai_ci")


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://logs_ai:synthetic@127.0.0.1:15432/logs_ai_test",
        "postgresql://logs_ai:synthetic@remote.example:15432/logs_ai_ci",
        "postgresql://logs_ai:synthetic@localhost:15432/logs_ai_ci",
        "postgresql://logs_ai:synthetic@127.0.0.1:5432/logs_ai_ci",
        "postgresql://other:synthetic@127.0.0.1:15432/logs_ai_ci",
        "postgresql://logs_ai:synthetic@127.0.0.1:15432/logs_ai_ci?hostaddr=192.0.2.1",
        "postgresql://logs_ai:synthetic@127.0.0.1:15432/logs_ai_ci?service=production",
    ],
)
def test_production_or_ambiguous_targets_are_rejected_before_connect(url):
    with pytest.raises(ValueError):
        validate_test_database(url)


@pytest.mark.parametrize("name", ["PGHOSTADDR", "PGSERVICE", "PGOPTIONS", "PGPASSWORD"])
def test_inherited_libpq_options_are_rejected(monkeypatch, name):
    monkeypatch.setenv(name, "synthetic")
    with pytest.raises(ValueError, match="inherited PG"):
        validate_test_database("postgresql://logs_ai:synthetic@127.0.0.1:15432/logs_ai_ci")


def test_alternative_listener_cannot_be_reached_via_pghostaddr(monkeypatch):
    with socket.socket() as listener:
        listener.bind(("127.0.0.2", 0))
        listener.listen()
        listener.settimeout(0.1)
        port = listener.getsockname()[1]
        monkeypatch.setenv("TEST_DATABASE_EXPECTED_PORT", str(port))
        monkeypatch.setenv("PGHOSTADDR", "127.0.0.2")
        with pytest.raises(ValueError, match="inherited PG"):
            connect_test_database(f"postgresql://logs_ai:synthetic@127.0.0.1:{port}/logs_ai_ci")
        with pytest.raises(TimeoutError):
            listener.accept()


def test_effective_destination_is_checked_before_sql(monkeypatch):
    conn = Mock()
    conn.info = SimpleNamespace(
        host="127.0.0.1", hostaddr="127.0.0.2", port=15432, dbname="logs_ai_ci", user="logs_ai"
    )
    connect = Mock(return_value=conn)
    monkeypatch.setattr(database_guard.psycopg, "connect", connect)
    with pytest.raises(ValueError, match="Effective database"):
        connect_test_database("postgresql://logs_ai:synthetic@127.0.0.1:15432/logs_ai_ci")
    assert connect.call_args.kwargs["hostaddr"] == "127.0.0.1"
    conn.close.assert_called_once()
    conn.execute.assert_not_called()
