import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("deploy", Path("scripts/deploy.py"))
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


@pytest.fixture(autouse=True)
def isolated_receipt(monkeypatch, tmp_path):
    # Unit fixtures use ephemeral paths; runner persistence policy has dedicated tests.
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("DOKPLOY_DEPLOYMENT_RECEIPT", str(tmp_path / "receipt.json"))
    monkeypatch.setenv("DOKPLOY_RECOVERY_FILE", str(tmp_path / "recovery.json"))


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
    monkeypatch.setattr(deploy, "verify_deployment_ref", lambda sha: "logs-ai-deploy-" + sha)
    monkeypatch.setenv("DOKPLOY_URL", "https://dokploy.example.com")
    monkeypatch.setenv("DOKPLOY_API_TOKEN", "test-only-token")
    monkeypatch.setenv("DOKPLOY_COMPOSE_ID", "logs-compose")
    monkeypatch.setenv("DOKPLOY_PROJECT_ID", "logs-project")
    monkeypatch.setenv("DOKPLOY_API_CONTRACT_VERIFIED", "true")
    monkeypatch.setenv("EXPECTED_REVISION", "a" * 40)
    environment = (
        "POSTGRES_PASSWORD="
        + "12" * 32
        + "\nAPP_BIND_HOST=127.0.0.1\nAPP_PORT=18000\nAPP_REVISION=old\nAPP_IMAGE=old\n"
    )
    snapshot = Path(deploy.os.environ["DOKPLOY_DEPLOYMENT_RECEIPT"]).with_name("compose.env")
    snapshot.write_text(environment)
    snapshot.chmod(0o600)
    monkeypatch.setenv("DOKPLOY_ENV_FILE", str(snapshot))
    return {
        "environment": {"projectId": "logs-project"},
        "sourceType": "git",
        "customGitUrl": "https://github.com/provedorconsult/logs-ai.git",
        "customGitBranch": "main",
        "composeType": "docker-compose",
        "composePath": "docker-compose.yml",
        "autoDeploy": False,
        "env": environment,
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
    url = "https://github.com/provedorconsult/logs-ai.git"
    responses = iter(["a" * 40, url, url, existing])
    monkeypatch.setattr(deploy, "git_transport", lambda *a: (["git"], {}))
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
    url = "https://github.com/provedorconsult/logs-ai.git"
    responses = iter(["a" * 40, url, url, "b" * 40])
    monkeypatch.setattr(deploy, "git_transport", lambda *a: (["git"], {}))
    monkeypatch.setattr(deploy.subprocess, "check_output", lambda *a, **k: next(responses))
    with pytest.raises(ValueError, match="different commit"):
        deploy.publish_deployment_ref("a" * 40)


def test_post_deploy_ref_check_cannot_recreate_missing_tag(monkeypatch):
    url = deploy.GIT_ORIGIN
    responses = iter(["a" * 40, url, url, "a" * 40 + "\trefs/tags/tag", "a" * 40, url, url, ""])
    monkeypatch.setattr(deploy.subprocess, "check_output", lambda *a, **k: next(responses))
    monkeypatch.setattr(deploy, "git_transport", lambda *a: (["git"], {}))
    monkeypatch.setattr(deploy.subprocess, "run", lambda *a, **k: pytest.fail("No second push"))
    deploy.publish_deployment_ref("a" * 40)
    with pytest.raises(ValueError, match="must not recreate"):
        deploy.verify_deployment_ref("a" * 40)


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


def test_returned_id_cannot_be_replaced_by_same_title(monkeypatch):
    monkeypatch.setattr(
        deploy,
        "api",
        lambda *a, **k: [
            {"deploymentId": "other", "composeId": "c", "status": "done", "title": "request"}
        ],
    )
    with pytest.raises(ValueError, match="match this request"):
        deploy.wait_deployment(
            "base", "synthetic", "c", set(), "request", {"deploymentId": "actual"}
        )


def test_title_fallback_ignores_history_when_api_has_no_id(monkeypatch):
    monkeypatch.setattr(
        deploy,
        "api",
        lambda *a, **k: [
            {"deploymentId": "old", "composeId": "c", "status": "done", "title": "request"},
            {"deploymentId": "new", "composeId": "c", "status": "done", "title": "request"},
        ],
    )
    record = deploy.wait_deployment("base", "synthetic", "c", {"old"}, "request", {})
    assert record["deploymentId"] == "new"


def test_returned_id_is_authoritative_when_server_changes_title(monkeypatch):
    monkeypatch.setattr(
        deploy,
        "api",
        lambda *a, **k: [
            {"deploymentId": "actual", "composeId": "c", "status": "done", "title": "server-title"},
        ],
    )
    record = deploy.wait_deployment(
        "base", "synthetic", "c", set(), "request", {"deploymentId": "actual"}
    )
    assert record["deploymentId"] == "actual"


@pytest.mark.parametrize(
    "pattern,expected",
    [
        ("refs/*", False),
        ("refs/tags/*", True),
        ("~ALL", True),
        ("refs/tags/logs-ai-deploy-*", True),
        ("refs/heads/*", False),
    ],
)
def test_ruleset_star_cannot_cross_slashes(pattern, expected):
    assert deploy.ref_pattern_matches(pattern, "refs/tags/logs-ai-deploy-" + "a" * 40) is expected


@pytest.mark.parametrize(
    "pattern", ["refs/**", "refs/tags/**", "refs/tags/[a-z]*", "~DEFAULT_BRANCH"]
)
def test_unsupported_rule_patterns_fail_closed(pattern):
    with pytest.raises(ValueError):
        deploy.ref_pattern_matches(pattern, "refs/tags/logs-ai-deploy-" + "a" * 40)


@pytest.mark.parametrize("change", ["omit", "redact", "extra", "manifest_permissions"])
def test_every_preserved_field_must_match_authoritative_manifest(monkeypatch, change):
    compose = configure_deploy(monkeypatch)
    snapshot = Path(deploy.os.environ["DOKPLOY_ENV_FILE"])
    complete = compose["env"] + "OTHER_SECRET=synthetic-value\n"
    snapshot.write_text(complete)
    current = complete
    if change == "omit":
        current = compose["env"]
    if change == "redact":
        current = complete.replace("synthetic-value", "********")
    if change == "extra":
        current += "UNKNOWN_SECRET=synthetic\n"
    if change == "manifest_permissions":
        snapshot.chmod(0o644)
    with pytest.raises(ValueError):
        deploy.revision_environment(current, "a" * 40)


def test_redacted_manifest_is_not_a_valid_source_of_truth(monkeypatch):
    compose = configure_deploy(monkeypatch)
    value = compose["env"] + "OTHER_SECRET=********\n"
    Path(deploy.os.environ["DOKPLOY_ENV_FILE"]).write_text(value)
    with pytest.raises(ValueError, match="redacted"):
        deploy.revision_environment(value, "a" * 40)


def test_complete_manifest_preserves_other_secrets_across_revision_changes(monkeypatch):
    compose = configure_deploy(monkeypatch)
    complete = compose["env"] + "OTHER_SECRET=synthetic-preserved-value\n"
    Path(deploy.os.environ["DOKPLOY_ENV_FILE"]).write_text(complete)
    actual = complete.replace("APP_REVISION=old", "APP_REVISION=" + "b" * 40)
    actual = actual.replace("APP_IMAGE=old", "APP_IMAGE=logs-ai:" + "b" * 40)
    result = deploy.revision_environment(actual, "a" * 40)
    assert "OTHER_SECRET=synthetic-preserved-value\n" in result
    assert "APP_REVISION=" + "a" * 40 in result


@pytest.mark.parametrize(
    "includes,excludes",
    [
        (["refs/*"], []),
        (["~ALL"], ["refs/tags/*"]),
        (["refs/**"], []),
        (["~ALL"], None),
    ],
)
def test_ruleset_ambiguous_or_excluded_coverage_cannot_authorize_deploy(
    monkeypatch, includes, excludes
):
    rule = {
        "id": 1,
        "target": "tag",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": includes, "exclude": excludes}},
        "rules": [{"type": "update"}, {"type": "deletion"}],
    }
    monkeypatch.setattr(
        deploy, "github_json", lambda p: [rule] if p.startswith("rulesets?") else rule
    )
    with pytest.raises(ValueError):
        deploy.require_immutable_tag("logs-ai-deploy-" + "a" * 40)


def test_git_specific_proxy_override_is_rejected_before_network(monkeypatch):
    monkeypatch.setenv("DOKPLOY_TRANSPORT", "direct")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv(
        "GIT_CONFIG_KEY_0", "http.https://github.com/provedorconsult/logs-ai.git.proxy"
    )
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "http://untrusted.invalid:8080")
    with pytest.raises(ValueError, match="conflicts"):
        deploy.git_transport()


@pytest.mark.parametrize(
    "fetch,push",
    [
        ("https://github.com/provedorconsult/logs-ai", deploy.GIT_ORIGIN),
        (deploy.GIT_ORIGIN, "https://github.com/provedorconsult/logs-ai"),
        (deploy.GIT_ORIGIN, "https://github.com:443/provedorconsult/logs-ai.git"),
    ],
)
def test_noncanonical_git_origins_cannot_start_network(monkeypatch, fetch, push):
    responses = iter(["a" * 40, fetch, push])
    monkeypatch.setattr(deploy.subprocess, "check_output", lambda *a, **k: next(responses))
    monkeypatch.setattr(
        deploy, "git_transport", lambda *a: pytest.fail("Must reject before transport")
    )
    with pytest.raises(ValueError, match="canonical"):
        deploy.publish_deployment_ref("a" * 40)


@pytest.mark.parametrize("value", ["1", "true", "0", ""])
@pytest.mark.parametrize("entrypoint", ["transport", "publish"])
def test_inherited_tls_override_is_rejected_before_git(monkeypatch, value, entrypoint):
    monkeypatch.setenv("DOKPLOY_TRANSPORT", "direct")
    monkeypatch.setenv("GIT_SSL_NO_VERIFY", value)
    monkeypatch.setattr(
        deploy.subprocess, "check_output", lambda *a, **k: pytest.fail("No Git call")
    )
    with pytest.raises(ValueError, match="GIT_SSL_NO_VERIFY"):
        if entrypoint == "transport":
            deploy.git_transport()
        else:
            deploy.publish_deployment_ref("a" * 40)


def test_effective_git_tls_configuration_cannot_disable_verification(monkeypatch):
    monkeypatch.setenv("DOKPLOY_TRANSPORT", "direct")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv(
        "GIT_CONFIG_KEY_0", "http.https://github.com/provedorconsult/logs-ai.git.sslVerify"
    )
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "false")
    with pytest.raises(ValueError, match="conflicts"):
        deploy.git_transport(deploy.GIT_ORIGIN)
