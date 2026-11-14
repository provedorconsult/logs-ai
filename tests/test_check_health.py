import importlib.util
import json
from pathlib import Path

import pytest

from tests.test_transport import listener

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


def configure_health(monkeypatch, tmp_path, origin):
    monkeypatch.setenv("DOKPLOY_TRANSPORT", "direct")
    monkeypatch.setenv("APP_TEST_URL", origin)
    monkeypatch.setenv("EXPECTED_REVISION", "a" * 40)
    monkeypatch.setenv("DOKPLOY_COMPOSE_ID", "c")
    path = tmp_path / "receipt.json"
    path.write_text(
        json.dumps(
            {
                "status": "done",
                "deploymentId": "new",
                "requestTitle": "nonce",
                "revision": "a" * 40,
                "composeId": "c",
            }
        )
    )
    monkeypatch.setenv("DOKPLOY_DEPLOYMENT_RECEIPT", str(path))
    monkeypatch.setattr(health.time, "sleep", lambda _: None)


def test_health_cannot_be_forged_by_inherited_proxy(monkeypatch, tmp_path):
    body = {"status": "ok", "database": "ok"}
    with listener(body=body, revision="a" * 40) as (attacker, forged), listener(503) as (origin, _):
        configure_health(monkeypatch, tmp_path, origin)
        monkeypatch.setenv("http_proxy", attacker)
        monkeypatch.setenv("HTTP_PROXY", attacker)
        monkeypatch.setenv("NO_PROXY", "")
        monkeypatch.setenv("no_proxy", "")
        with pytest.raises(SystemExit):
            health.main()
        assert forged == []


def test_health_does_not_follow_redirect_to_matching_fake_revision(monkeypatch, tmp_path):
    body = {"status": "ok", "database": "ok"}
    with (
        listener(body=body, revision="a" * 40) as (attacker, forged),
        listener(302, attacker) as (origin, _),
    ):
        configure_health(monkeypatch, tmp_path, origin)
        with pytest.raises(SystemExit):
            health.main()
        assert forged == []


def test_health_accepts_matching_response_from_exact_origin(monkeypatch, tmp_path):
    with listener(body={"status": "ok", "database": "ok"}, revision="a" * 40) as (origin, received):
        configure_health(monkeypatch, tmp_path, origin)
        health.main()
        assert len(received) == 1
