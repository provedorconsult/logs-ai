import copy

import pytest
from test_deploy import configure_deploy, deploy


@pytest.fixture(autouse=True)
def local_recovery_fixture(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)


@pytest.fixture
def interrupted_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv("DOKPLOY_DEPLOYMENT_RECEIPT", str(tmp_path / "receipt.json"))
    monkeypatch.setenv("DOKPLOY_RECOVERY_FILE", str(tmp_path / "recovery.json"))
    compose = configure_deploy(monkeypatch)
    compose["command"] = ""
    before = copy.deepcopy(compose)
    state = copy.deepcopy(compose)
    control = {
        "failSave": True,
        "saveApplied": False,
        "failRestore": False,
        "deployments": [],
    }
    calls = []

    def api(base, token, route, data=None, query=None):
        calls.append((route, data))
        if route == "compose.one":
            return copy.deepcopy(state)
        if route == "deployment.allByCompose":
            return copy.deepcopy(control["deployments"])
        if route == "compose.update":
            if control["failRestore"] and data.get("customGitBranch") == "main":
                control["failRestore"] = False
                raise RuntimeError("synthetic restore failure")
            state.update({k: v for k, v in data.items() if k != "composeId"})
        if route == "compose.saveEnvironment":
            if not control["failSave"] or control["saveApplied"]:
                state["env"] = data["env"]
            if control["failSave"]:
                raise RuntimeError("synthetic save failure")
        if route == "compose.deploy":
            raise RuntimeError("synthetic ambiguous deployment request")

    monkeypatch.setattr(deploy, "api", api)
    monkeypatch.setattr(deploy, "publish_deployment_ref", lambda sha: "logs-ai-deploy-" + sha)
    return before, state, control, calls


@pytest.mark.parametrize("save_applied", [False, True])
def test_failed_save_preserves_journal_and_can_restore_before_request(
    interrupted_configuration, save_applied
):
    before, state, control, calls = interrupted_configuration
    control["saveApplied"] = save_applied
    with pytest.raises(RuntimeError, match="save failure"):
        deploy.deploy()
    journal = deploy.read_recovery(deploy.recovery_path())
    assert journal["phase"] == "prepared"
    assert not any(route == "compose.deploy" for route, _ in calls)
    assert state["customGitBranch"] != before["customGitBranch"]
    control["failSave"] = False
    deploy.reconcile()
    assert state == before
    assert not deploy.recovery_path().exists()


@pytest.mark.parametrize("change", ["env", "source", "deployment"])
def test_recovery_refuses_external_changes_without_writes(interrupted_configuration, change):
    _, state, control, calls = interrupted_configuration
    with pytest.raises(RuntimeError):
        deploy.deploy()
    control["failSave"] = False
    if change == "env":
        state["env"] = "external change"
    elif change == "source":
        state["owner"] = "other-owner"
    else:
        control["deployments"] = [{"deploymentId": "external", "status": "done"}]
    calls.clear()
    with pytest.raises(ValueError, match="External change"):
        deploy.reconcile()
    assert all(data is None for _, data in calls)
    assert deploy.recovery_path().exists()


def test_recovery_refuses_ambiguous_deployment_request(interrupted_configuration):
    _, _, control, calls = interrupted_configuration
    control["failSave"] = False
    with pytest.raises(RuntimeError, match="ambiguous deployment"):
        deploy.deploy()
    assert deploy.read_recovery(deploy.recovery_path())["phase"] == "deployment_requested"
    calls.clear()
    with pytest.raises(ValueError, match="no deployment request"):
        deploy.reconcile()
    assert calls == []


def test_interrupted_recovery_can_retry_without_deploy_or_tag_mutation(interrupted_configuration):
    before, state, control, calls = interrupted_configuration
    control["saveApplied"] = True
    with pytest.raises(RuntimeError):
        deploy.deploy()
    control["failSave"] = False
    control["failRestore"] = True
    with pytest.raises(RuntimeError, match="restore failure"):
        deploy.reconcile()
    assert deploy.recovery_path().exists()
    deploy.reconcile()
    assert state == before
    assert not any(route == "compose.deploy" for route, _ in calls)


def test_recovery_cannot_override_target_resource_id(interrupted_configuration):
    _, _, _, calls = interrupted_configuration
    with pytest.raises(RuntimeError):
        deploy.deploy()
    path = deploy.recovery_path()
    record = deploy.read_recovery(path)
    record["before"]["composeId"] = "foreign-resource"
    record["planned"]["composeId"] = "foreign-resource"
    deploy.write_recovery(path, record)
    calls.clear()
    with pytest.raises(ValueError, match="unsupported configuration"):
        deploy.reconcile()
    assert calls == []


def test_preexisting_journal_is_preserved_and_blocks_new_attempt(monkeypatch, tmp_path):
    path = tmp_path / "pending.json"
    path.write_text("existing recovery record")
    monkeypatch.setenv("DOKPLOY_RECOVERY_FILE", str(path))
    monkeypatch.setenv("DOKPLOY_DEPLOYMENT_RECEIPT", str(tmp_path / "receipt.json"))
    monkeypatch.setattr(deploy, "api", lambda *a, **k: pytest.fail("No API calls"))
    with pytest.raises(ValueError, match="existing recovery"):
        deploy.deploy()
    assert path.read_text() == "existing recovery record"


@pytest.mark.parametrize("root", ["GITHUB_WORKSPACE", "RUNNER_TEMP"])
def test_runner_journal_cannot_be_lost_to_checkout_or_temporary_cleanup(
    monkeypatch, tmp_path, root
):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv(root, str(tmp_path))
    monkeypatch.setenv("DOKPLOY_RECOVERY_FILE", str(tmp_path / "recovery.json"))
    with pytest.raises(ValueError, match="must survive"):
        deploy.recovery_path()
