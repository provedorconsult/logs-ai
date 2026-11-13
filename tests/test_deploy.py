import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("deploy", Path("scripts/deploy.py"))
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


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
        "env": "POSTGRES_PASSWORD=test-only-password\nAPP_REVISION=old\nAPP_IMAGE=old\n",
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
        if route == "compose.getDefaultCommand":
            return "docker compose -p logs-ai --env-file .env up -d --build"

    monkeypatch.setattr(deploy, "api", api)
    monkeypatch.setattr(deploy, "publish_deployment_ref", lambda sha: "logs-ai-deploy-" + sha)
    deploy.deploy()
    assert [route for route, _ in calls] == [
        "compose.one",
        "compose.getDefaultCommand",
        "compose.update",
        "compose.saveEnvironment",
        "compose.deploy",
    ]
    command = calls[2][1]["command"]
    assert command == "docker compose -p logs-ai --env-file .env up -d --build"
    assert calls[2][1]["branch" if source == "github" else "customGitBranch"] == (
        "logs-ai-deploy-" + "a" * 40
    )
    environment = calls[3][1]["env"]
    assert "POSTGRES_PASSWORD=test-only-password\n" in environment
    assert "APP_REVISION=" + "a" * 40 in environment
    assert "APP_IMAGE=logs-ai:" + "a" * 40 in environment
    assert "=old" not in environment


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
