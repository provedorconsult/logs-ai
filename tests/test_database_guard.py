import pytest
from database_guard import validate_test_database


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
