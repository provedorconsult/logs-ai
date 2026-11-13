import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("deploy", Path("scripts/deploy.py"))
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


@pytest.fixture(autouse=True)
def isolated_receipt(monkeypatch, tmp_path):
    monkeypatch.setenv("DOKPLOY_DEPLOYMENT_RECEIPT", str(tmp_path / "receipt.json"))


@pytest.mark.parametrize(
    "url",
    [
        "http://100.80.0.1:3000",
        "https://token:secret@example.com",
        "https://example.com?token=secret",
        "https://example.com/path",
        "file:///tmp/token",
    ],
)
def test_unsafe_administrative_url_is_rejected(url):
    with pytest.raises(ValueError):
        deploy.validate_url(url)


def test_tunnel_requires_explicit_validation(monkeypatch):
    monkeypatch.delenv("DOKPLOY_SSH_TUNNEL_VERIFIED", raising=False)
    with pytest.raises(ValueError):
        deploy.validate_url("http://127.0.0.1:13000")
    monkeypatch.setenv("DOKPLOY_SSH_TUNNEL_VERIFIED", "true")
    assert deploy.validate_url("http://127.0.0.1:13000") == "http://127.0.0.1:13000"


def test_https_origin_is_accepted():
    assert deploy.validate_url("https://dokploy.example.com/") == "https://dokploy.example.com"


def test_redirect_is_rejected():
    assert deploy.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other") is None


def test_tailnet_http_requires_authorization_and_exact_origin(monkeypatch):
    origin = "http://server.example.ts.net:3000"
    monkeypatch.setenv("DOKPLOY_TAILNET_HTTP_ORIGIN", origin)
    monkeypatch.delenv("DOKPLOY_ALLOW_TAILNET_HTTP", raising=False)
    with pytest.raises(ValueError):
        deploy.validate_url(origin)
    monkeypatch.setenv("DOKPLOY_ALLOW_TAILNET_HTTP", "true")
    assert deploy.validate_url(origin + "/") == origin
    for other in ["http://other.example.ts.net:3000", "http://server.example.ts.net:80"]:
        with pytest.raises(ValueError):
            deploy.validate_url(other)
    monkeypatch.setenv("DOKPLOY_TAILNET_HTTP_ORIGIN", "http://public.example.com:3000")
    with pytest.raises(ValueError):
        deploy.validate_url("http://public.example.com:3000")


def configure_deploy(monkeypatch):
    monkeypatch.setenv("DOKPLOY_TRANSPORT", "direct")
    monkeypatch.setattr(deploy, "require_immutable_tag", lambda tag: None)
    monkeypatch.setenv("DOKPLOY_URL", "https://dokploy.example.com")
    monkeypatch.setenv("DOKPLOY_API_TOKEN", "test-only-token")
    monkeypatch.setenv("DOKPLOY_COMPOSE_ID", "logs-compose")
    monkeypatch.setenv("DOKPLOY_PROJECT_ID", "logs-project")
    monkeypatch.setenv("DOKPLOY_API_CONTRACT_VERIFIED", "true")
    monkeypatch.setenv("EXPECTED_REVISION", "a" * 40)
    return {
        "environment": {"projectId": "logs-project"},
        "sourceType": "git",
        "customGitUrl": "https://github.com/provedorconsult/logs-ai.git",
        "customGitBranch": "main",
        "composeType": "docker-compose",
        "composePath": "docker-compose.yml",
        "autoDeploy": False,
        "env": "POSTGRES_PASSWORD=" + "12" * 32 + "\nAPP_REVISION=old\nAPP_IMAGE=old\n",
    }


@pytest.mark.parametrize("source", ["git", "github"])
def test_deploy_guards_source_and_preserves_database_secret(monkeypatch, source):
    compose = configure_deploy(monkeypatch)
    if source == "github":
        compose.update(
            sourceType="github",
            owner="provedorconsult",
            repository="logs-ai",
            branch="main",
            githubId="test-provider",
        )
    calls = []

    def api(base, token, route, data=None, query=None):
        calls.append((route, data))
        if route == "compose.one":
            return compose
        if route == "deployment.allByCompose":
            return (
                []
                if len(calls) == 2
                else [{"deploymentId": "new", "composeId": "logs-compose", "status": "done"}]
            )
        if route == "compose.deploy":
            return {"deploymentId": "new"}

    monkeypatch.setattr(deploy, "api", api)
    monkeypatch.setattr(deploy, "publish_deployment_ref", lambda sha: "logs-ai-deploy-" + sha)
    deploy.deploy()
    assert [route for route, _ in calls] == [
        "compose.one",
        "deployment.allByCompose",
        "compose.update",
        "compose.saveEnvironment",
        "compose.deploy",
        "deployment.allByCompose",
    ]
    assert calls[2][1]["command"] == ""
    assert calls[2][1]["branch" if source == "github" else "customGitBranch"] == (
        "logs-ai-deploy-" + "a" * 40
    )
    environment = calls[3][1]["env"]
    assert "POSTGRES_PASSWORD=" + "12" * 32 + "\n" in environment
    assert "APP_REVISION=" + "a" * 40 in environment
    assert "APP_IMAGE=logs-ai:" + "a" * 40 in environment
    assert "=old" not in environment
    receipt = json.loads(Path(deploy.os.environ["DOKPLOY_DEPLOYMENT_RECEIPT"]).read_text())
    assert receipt["deploymentId"] == "new"
    assert receipt["status"] == "done"


@pytest.mark.parametrize("field", ["project", "repository", "autoDeploy"])
def test_deploy_rejects_wrong_resource_before_mutating(monkeypatch, field):
    compose = configure_deploy(monkeypatch)
    if field == "project":
        compose["environment"]["projectId"] = "other-project"
    elif field == "repository":
        compose["customGitUrl"] = "https://github.com/other/repo.git"
    else:
        compose["autoDeploy"] = True
    calls = []

    def api(base, token, route, data=None, query=None):
        calls.append(route)
        return compose

    monkeypatch.setattr(deploy, "api", api)
    with pytest.raises(ValueError):
        deploy.deploy()
    assert calls == ["compose.one"]


@pytest.mark.parametrize("existing", ["", "a" * 40 + "\trefs/tags/test"])
def test_deployment_ref_published_once_without_force(monkeypatch, existing):
    responses = iter(["a" * 40, "https://github.com/provedorconsult/logs-ai.git", existing])
    monkeypatch.setattr(deploy.subprocess, "check_output", lambda *a, **k: next(responses))
    pushed = []
    monkeypatch.setattr(deploy.subprocess, "run", lambda args, **k: pushed.append(args))
    assert deploy.publish_deployment_ref("a" * 40) == "logs-ai-deploy-" + "a" * 40
    assert len(pushed) == (0 if existing else 1)
    if pushed:
        assert pushed[0] == [
            "git",
            "push",
            "origin",
            "a" * 40 + ":refs/tags/logs-ai-deploy-" + "a" * 40,
        ]


def test_existing_deployment_ref_cannot_be_retargeted(monkeypatch):
    responses = iter(["a" * 40, "https://github.com/provedorconsult/logs-ai.git", "b" * 40])
    monkeypatch.setattr(deploy.subprocess, "check_output", lambda *a, **k: next(responses))
    with pytest.raises(ValueError, match="different commit"):
        deploy.publish_deployment_ref("a" * 40)


@pytest.mark.parametrize("value", [None, "", "APP_REVISION=old\n", "POSTGRES_PASSWORD=REDACTED\n"])
def test_partial_environment_fails_before_any_write(monkeypatch, value):
    compose = configure_deploy(monkeypatch)
    compose["env"] = value
    calls = []

    def api(base, token, route, data=None, query=None):
        calls.append(route)
        return compose

    monkeypatch.setattr(deploy, "api", api)
    with pytest.raises(ValueError):
        deploy.deploy()
    assert calls == ["compose.one"]


def test_missing_environment_does_not_reuse_old_receipt(monkeypatch):
    compose = configure_deploy(monkeypatch)
    del compose["env"]
    path = Path(deploy.os.environ["DOKPLOY_DEPLOYMENT_RECEIPT"])
    path.write_text('{"status":"done"}')
    monkeypatch.setattr(deploy, "api", lambda *a, **k: compose)
    with pytest.raises(ValueError):
        deploy.deploy()
    assert not path.exists()


def test_tag_policy_requires_active_update_and_deletion_rules(monkeypatch):
    monkeypatch.setattr(deploy, "github_json", lambda path: [])
    with pytest.raises(ValueError, match="protection"):
        deploy.require_immutable_tag("logs-ai-deploy-" + "a" * 40)


def test_unprotected_tags_stop_deploy_before_any_remote_write(monkeypatch):
    compose = configure_deploy(monkeypatch)
    calls = []

    def api(base, token, route, data=None, query=None):
        calls.append(route)
        assert data is None
        return compose if route == "compose.one" else []

    def denied(tag):
        raise ValueError("No verified protection")

    monkeypatch.setattr(deploy, "api", api)
    monkeypatch.setattr(deploy, "require_immutable_tag", denied)
    monkeypatch.setattr(
        deploy, "publish_deployment_ref", lambda _: pytest.fail("Must not push tags")
    )
    with pytest.raises(ValueError, match="protection"):
        deploy.deploy()
    assert calls == ["compose.one", "deployment.allByCompose"]


@pytest.mark.parametrize("change", [None, "bypass", "exclude", "inactive", "missing_deletion"])
def test_tag_policy_checks_effective_rules(monkeypatch, change):
    rule = {
        "id": 1,
        "target": "tag",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["refs/tags/logs-ai-deploy-*"], "exclude": []}},
        "rules": [{"type": "update"}, {"type": "deletion"}],
    }
    if change == "bypass":
        rule["bypass_actors"] = [{"actor_type": "RepositoryRole", "actor_id": 5}]
    if change == "exclude":
        rule["conditions"]["ref_name"]["exclude"] = ["refs/tags/logs-ai-deploy-*"]
    if change == "inactive":
        rule["enforcement"] = "evaluate"
    if change == "missing_deletion":
        rule["rules"] = [{"type": "update"}]
    monkeypatch.setattr(
        deploy, "github_json", lambda path: [rule] if path.startswith("rulesets?") else rule
    )
    if change:
        with pytest.raises(ValueError):
            deploy.require_immutable_tag("logs-ai-deploy-" + "a" * 40)
    else:
        deploy.require_immutable_tag("logs-ai-deploy-" + "a" * 40)


def test_deployment_failure_cannot_approve_an_already_healthy_revision(monkeypatch):
    monkeypatch.setattr(
        deploy,
        "api",
        lambda *a, **k: [
            {"deploymentId": "old", "composeId": "c", "status": "done", "title": "same-sha"},
            {"deploymentId": "new", "composeId": "c", "status": "error", "title": "request"},
        ],
    )
    with pytest.raises(RuntimeError, match="successfully"):
        deploy.wait_deployment("base", "synthetic", "c", {"old"}, "request", {})


def test_pending_request_times_out_instead_of_accepting_old_success(monkeypatch):
    monkeypatch.setenv("DOKPLOY_DEPLOY_TIMEOUT", "1")
    clock = iter([0, 0, 2])
    monkeypatch.setattr(deploy.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(deploy.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        deploy,
        "api",
        lambda *a, **k: [
            {"deploymentId": "old", "composeId": "c", "status": "done", "title": "same-sha"},
        ],
    )
    with pytest.raises(RuntimeError, match="timed out"):
        deploy.wait_deployment("base", "synthetic", "c", {"old"}, "request", {})


def test_deployment_must_be_correlated_to_this_request(monkeypatch):
    monkeypatch.setattr(
        deploy,
        "api",
        lambda *a, **k: [
            {"deploymentId": "other", "composeId": "c", "status": "done", "title": "unrelated"},
        ],
    )
    with pytest.raises(ValueError, match="match this request"):
        deploy.wait_deployment("base", "synthetic", "c", set(), "request", {})
