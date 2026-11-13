"""Trigger the configured Dokploy Compose resource without logging credentials."""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_url(value):
    url = urllib.parse.urlsplit(value)
    if url.username or url.password or url.query or url.fragment:
        raise ValueError("Administrative URL must not contain credentials, query or fragment")
    if url.scheme != "https":
        authorized_tailnet = (
            os.environ.get("DOKPLOY_ALLOW_TAILNET_HTTP") == "true"
            and value.rstrip("/") == os.environ.get("DOKPLOY_TAILNET_HTTP_ORIGIN")
            and url.hostname
            and url.hostname.endswith(".ts.net")
        )
        if not (
            url.scheme == "http"
            and (
                authorized_tailnet
                or (
                    url.hostname in {"127.0.0.1", "localhost", "::1"}
                    and os.environ.get("DOKPLOY_SSH_TUNNEL_VERIFIED") == "true"
                )
            )
        ):
            raise ValueError(
                "Use HTTPS, a verified SSH tunnel or an explicitly authorized Tailnet origin"
            )
    if not url.hostname or url.path not in {"", "/"}:
        raise ValueError("Configure the administrative origin only")
    return value.rstrip("/")


def api(base, token, route, data=None, query=None):
    url = base + "/api/" + route
    if query:
        url += "?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Content-Type": "application/json", "x-api-key": token},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
        body = response.read()
        return json.loads(body) if body else None


def revision_environment(value, revision):
    lines = [
        line
        for line in (value or "").splitlines()
        if not re.match(r"^\s*(?:export\s+)?(?:APP_REVISION|APP_IMAGE)\s*=", line)
    ]
    return "\n".join([*lines, f"APP_REVISION={revision}", f"APP_IMAGE=logs-ai:{revision}", ""])


def deploy():
    base = validate_url(os.environ["DOKPLOY_URL"])
    token = os.environ.get("DOKPLOY_API_TOKEN") or os.environ["dokploy_token"]
    compose_id = os.environ["DOKPLOY_COMPOSE_ID"]
    if not token or not compose_id or compose_id.startswith("substitua_"):
        raise ValueError("Configure token and Compose resource")
    if os.environ.get("DOKPLOY_API_CONTRACT_VERIFIED") != "true":
        raise ValueError("Verify Compose API contracts against this Dokploy instance first")
    revision = os.environ["EXPECTED_REVISION"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("EXPECTED_REVISION must be a full Git SHA")
    project_id = os.environ["DOKPLOY_PROJECT_ID"]
    compose = api(base, token, "compose.one", query={"composeId": compose_id})
    source_matches = (
        compose.get("sourceType") == "git"
        and compose.get("customGitUrl") == "https://github.com/provedorconsult/logs-ai.git"
        and compose.get("customGitBranch") == "main"
    ) or (
        compose.get("sourceType") == "github"
        and compose.get("owner") == "provedorconsult"
        and compose.get("repository") == "logs-ai"
        and compose.get("branch") == "main"
        and bool(compose.get("githubId"))
    )
    if (
        not project_id
        or compose.get("environment", {}).get("projectId") != project_id
        or not source_matches
        or compose.get("composeType") != "docker-compose"
        or compose.get("composePath") != "docker-compose.yml"
        or compose.get("autoDeploy")
    ):
        raise ValueError("Compose must belong to the configured logs-ai project and Git source")
    command = api(base, token, "compose.getDefaultCommand", query={"composeId": compose_id})
    if not isinstance(command, str) or not command.startswith("docker compose "):
        raise ValueError("Unexpected Dokploy Compose command")
    # Abort before building if main advanced after CI. The label must describe actual source.
    command = f'test "$(git rev-parse HEAD)" = {revision} && {command}'
    api(
        base,
        token,
        "compose.update",
        {"composeId": compose_id, "command": command},
    )
    api(
        base,
        token,
        "compose.saveEnvironment",
        {"composeId": compose_id, "env": revision_environment(compose.get("env"), revision)},
    )
    api(base, token, "compose.deploy", {"composeId": compose_id, "title": f"G02 {revision}"})
    print("Dokploy accepted deployment request; remote readiness still needs verification")


if __name__ == "__main__":
    try:
        deploy()
    except (KeyError, ValueError, urllib.error.URLError, RuntimeError):
        print("Deploy failed: verify configuration, transport and API contract", file=sys.stderr)
        sys.exit(1)
