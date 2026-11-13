import json
import os
from pathlib import Path

import pytest
import snapshot


def test_only_new_snapshot_is_cleaned_up(tmp_path):
    preexisting = tmp_path / "compose.env"
    preexisting.write_text("preexisting")
    record = snapshot.materialize("synthetic-secret", tmp_path)
    path = Path(record["path"])
    assert path.read_text() == "synthetic-secret"
    assert path.stat().st_mode & 0o777 == 0o600
    snapshot.cleanup(record)
    assert preexisting.read_text() == "preexisting"
    assert not Path(record["directory"]).exists()


def test_creation_failure_and_unconditional_cleanup_preserve_preexisting_file(
    monkeypatch, tmp_path
):
    existing = tmp_path / "compose.env"
    existing.write_text("preexisting")
    monkeypatch.setattr(snapshot.tempfile, "mkdtemp", lambda **k: str(tmp_path))
    with pytest.raises(FileExistsError):
        snapshot.materialize("synthetic-secret", tmp_path)
    monkeypatch.setenv("DOKPLOY_ENV_FILE", str(existing))
    monkeypatch.delenv("DOKPLOY_SNAPSHOT_OWNERSHIP", raising=False)
    monkeypatch.setattr(snapshot.sys, "argv", ["snapshot.py", "cleanup"])
    snapshot.main()
    assert existing.read_text() == "preexisting"


def test_replaced_file_is_not_deleted(tmp_path):
    record = snapshot.materialize("synthetic-secret", tmp_path)
    path = Path(record["path"])
    path.rename(path.with_name("original.env"))
    path.write_text("foreign replacement")
    with pytest.raises(ValueError, match="replaced"):
        snapshot.cleanup(record)
    assert path.read_text() == "foreign replacement"


def test_export_failure_removes_only_owned_snapshot(monkeypatch, tmp_path):
    storage = tmp_path / "storage"
    storage.mkdir()
    monkeypatch.setenv("RUNNER_TEMP", str(storage))
    monkeypatch.setenv("DOKPLOY_ENV_SNAPSHOT", "synthetic-secret")
    monkeypatch.setenv("GITHUB_ENV", str(tmp_path))  # Directory: export must fail.
    monkeypatch.setattr(snapshot.sys, "argv", ["snapshot.py", "create"])
    with pytest.raises(OSError):
        snapshot.main()
    assert list(storage.iterdir()) == []


def test_export_contains_ownership_and_not_the_secret(monkeypatch, tmp_path):
    envfile = tmp_path / "github.env"
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("DOKPLOY_ENV_SNAPSHOT", "synthetic-secret")
    monkeypatch.setenv("GITHUB_ENV", str(envfile))
    monkeypatch.setattr(snapshot.sys, "argv", ["snapshot.py", "create"])
    snapshot.main()
    value = envfile.read_text()
    assert "synthetic-secret" not in value
    record = json.loads(value.split("DOKPLOY_SNAPSHOT_OWNERSHIP=", 1)[1])
    assert os.stat(record["path"]).st_mode & 0o077 == 0
    snapshot.cleanup(record)
