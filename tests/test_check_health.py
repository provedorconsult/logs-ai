import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("check_health", Path("scripts/check_health.py"))
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


def test_configured_compose_requires_default_receipt(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOKPLOY_DEPLOYMENT_RECEIPT", raising=False)
    monkeypatch.setenv("DOKPLOY_COMPOSE_ID", "c")
    with pytest.raises(FileNotFoundError):
        health.require_deployment_receipt()


@pytest.mark.parametrize("change", [None, "error", "revision", "composeId", "missing"])
def test_readiness_receipt_must_match_completed_deployment(monkeypatch, tmp_path, change):
    path = tmp_path / "receipt.json"
    monkeypatch.setenv("DOKPLOY_DEPLOYMENT_RECEIPT", str(path))
    monkeypatch.setenv("EXPECTED_REVISION", "a" * 40)
    monkeypatch.setenv("DOKPLOY_COMPOSE_ID", "c")
    record = {
        "deploymentId": "new",
        "composeId": "c",
        "status": "done",
        "revision": "a" * 40,
        "requestTitle": "unique-request",
    }
    if change == "error":
        record["status"] = "error"
    if change == "revision":
        record["revision"] = "b" * 40
    if change == "composeId":
        record["composeId"] = "other"
    if change != "missing":
        path.write_text(json.dumps(record))
    if change:
        with pytest.raises((ValueError, FileNotFoundError)):
            health.require_deployment_receipt()
    else:
        health.require_deployment_receipt()
