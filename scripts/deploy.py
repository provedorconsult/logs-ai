"""Trigger the configured Dokploy Compose resource without logging credentials."""

import fnmatch
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PinnedProxy(urllib.request.ProxyHandler):
    def proxy_open(self, req, proxy, type):
        # Proxy selection is explicit; inherited NO_PROXY must not change it.
        req.set_proxy(urllib.parse.urlsplit(proxy).netloc, "http")
        return None


def approved_opener():
    mode = os.environ.get("DOKPLOY_TRANSPORT")
    if mode == "direct":
        handler = urllib.request.ProxyHandler({})
    elif mode == "proxy":
        proxy = os.environ.get("DOKPLOY_APPROVED_PROXY", "")
        parsed = urllib.parse.urlsplit(proxy)
        if (
            parsed.scheme != "http"
            or not parsed.hostname
            or not parsed.port
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Configure the exact approved HTTP proxy origin")
        handler = PinnedProxy({"http": proxy, "https": proxy})
    else:
        raise ValueError("Explicitly select direct or approved proxy transport")
    return urllib.request.build_opener(handler, NoRedirect())


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
    with approved_opener().open(request, timeout=30) as response:
        body = response.read()
        return json.loads(body) if body else None


def revision_environment(value, revision):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Compose environment is missing or redacted; refusing to replace it")
    passwords = re.findall(r"^POSTGRES_PASSWORD=([^\r\n]*)$", value, re.MULTILINE)
    if len(passwords) != 1 or not re.fullmatch(r"[0-9a-fA-F]{32,128}", passwords[0]):
        raise ValueError("Compose requires one configured hexadecimal PostgreSQL secret")
    lines = [
        line
        for line in value.splitlines()
        if not re.match(r"^\s*(?:export\s+)?(?:APP_REVISION|APP_IMAGE)\s*=", line)
    ]
    return "\n".join([*lines, f"APP_REVISION={revision}", f"APP_IMAGE=logs-ai:{revision}", ""])


def github_json(path):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(
        "https://api.github.com/repos/provedorconsult/logs-ai/" + path, headers=headers
    )
    with approved_opener().open(request, timeout=30) as response:
        return json.load(response)


def require_immutable_tag(tag):
    rulesets = github_json("rulesets?includes_parents=true")
    if not isinstance(rulesets, list):
        raise ValueError("Cannot verify remote tag protection")
    covered = set()
    ref = "refs/tags/" + tag
    for summary in rulesets:
        if summary.get("target") != "tag" or summary.get("enforcement") != "active":
            continue
        rule = github_json("rulesets/" + str(int(summary["id"])))
        if (
            rule.get("target") != "tag"
            or rule.get("enforcement") != "active"
            or rule.get("bypass_actors") != []
        ):
            continue
        names = rule.get("conditions", {}).get("ref_name", {})
        includes = names.get("include", [])
        excludes = names.get("exclude", [])
        if any(p == "~ALL" or fnmatch.fnmatchcase(ref, p) for p in includes) and not any(
            p == "~ALL" or fnmatch.fnmatchcase(ref, p) for p in excludes
        ):
            covered.update(r.get("type") for r in rule.get("rules", []))
    if not {"update", "deletion"} <= covered:
        raise ValueError("Active remote tag update/deletion protection without bypass is required")


def wait_deployment(base, token, compose_id, previous_ids, title, result):
    timeout = int(os.environ.get("DOKPLOY_DEPLOY_TIMEOUT", "600"))
    if not 1 <= timeout <= 3600:
        raise ValueError("Invalid deployment timeout")
    deadline = time.monotonic() + timeout
    returned_id = result.get("deploymentId") if isinstance(result, dict) else None
    if returned_id in previous_ids:
        raise ValueError("API returned an old deployment")
    while time.monotonic() < deadline:
        records = api(base, token, "deployment.allByCompose", query={"composeId": compose_id})
        new = [d for d in records if d.get("deploymentId") not in previous_ids]
        if len(new) > 1:
            raise ValueError("Concurrent deployments prevent unambiguous request correlation")
        if new:
            record = new[0]
            if record.get("composeId") != compose_id or (
                record.get("deploymentId") != returned_id and record.get("title") != title
            ):
                raise ValueError("New deployment does not match this request")
            if record.get("status") == "done":
                return record
            if record.get("status") not in {"queued", "running"}:
                raise RuntimeError("Requested deployment did not complete successfully")
        time.sleep(2)
    raise RuntimeError("Requested deployment timed out")


def publish_deployment_ref(revision):
    if subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() != revision:
        raise ValueError("Local checkout does not match EXPECTED_REVISION")
    remote = urllib.parse.urlsplit(
        subprocess.check_output(["git", "remote", "get-url", "origin"], text=True).strip()
    )
    if remote.hostname != "github.com" or remote.path not in {
        "/provedorconsult/logs-ai",
        "/provedorconsult/logs-ai.git",
    }:
        raise ValueError("Deployment refs may only be published to logs-ai")
    tag = f"logs-ai-deploy-{revision}"
    ref = f"refs/tags/{tag}"
    existing = subprocess.check_output(["git", "ls-remote", "origin", ref], text=True).strip()
    if existing:
        if existing.split()[0] != revision:
            raise ValueError("Deployment ref already points to a different commit")
    else:
        # Never overwrite a deployment ref, including on retry.
        subprocess.run(
            ["git", "push", "origin", f"{revision}:{ref}"],
            check=True,
            capture_output=True,
        )
    return tag


def deploy():
    receipt = Path(os.environ.get("DOKPLOY_DEPLOYMENT_RECEIPT", "work/dokploy-deployment.json"))
    receipt.unlink(missing_ok=True)
    approved_opener()  # Validate transport before any authenticated request.
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
    branch_field = "branch" if compose.get("sourceType") == "github" else "customGitBranch"
    branch = compose.get(branch_field) or ""
    branch_matches = branch == "main" or bool(re.fullmatch(r"logs-ai-deploy-[0-9a-f]{40}", branch))
    source_matches = (
        compose.get("sourceType") == "git"
        and compose.get("customGitUrl") == "https://github.com/provedorconsult/logs-ai.git"
    ) or (
        compose.get("sourceType") == "github"
        and compose.get("owner") == "provedorconsult"
        and compose.get("repository") == "logs-ai"
        and bool(compose.get("githubId"))
    )
    if (
        not project_id
        or compose.get("environment", {}).get("projectId") != project_id
        or not source_matches
        or not branch_matches
        or compose.get("composeType") != "docker-compose"
        or compose.get("composePath") != "docker-compose.yml"
        or compose.get("autoDeploy")
    ):
        raise ValueError("Compose must belong to the configured logs-ai project and Git source")
    environment = revision_environment(compose.get("env"), revision)
    previous = api(base, token, "deployment.allByCompose", query={"composeId": compose_id})
    if not isinstance(previous, list) or any(
        d.get("status") != "done" and d.get("status") != "error" for d in previous
    ):
        raise ValueError("Wait for existing deployments before modifying this Compose")
    previous_ids = {d["deploymentId"] for d in previous}
    tag = f"logs-ai-deploy-{revision}"
    require_immutable_tag(tag)
    publish_deployment_ref(revision)
    api(
        base,
        token,
        "compose.update",
        # An empty override selects Dokploy's native command. Its preview includes
        # the docker executable, whereas the override field expects only arguments.
        {"composeId": compose_id, "command": "", branch_field: tag},
    )
    api(
        base,
        token,
        "compose.saveEnvironment",
        {"composeId": compose_id, "env": environment},
    )
    title = f"G02 {revision} {uuid.uuid4().hex}"
    result = api(base, token, "compose.deploy", {"composeId": compose_id, "title": title})
    record = wait_deployment(base, token, compose_id, previous_ids, title, result)
    require_immutable_tag(tag)
    publish_deployment_ref(revision)  # Also recheck the ref after the remote build.
    receipt.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as file:
        json.dump(
            {
                "composeId": compose_id,
                "deploymentId": record["deploymentId"],
                "revision": revision,
                "status": "done",
                "requestTitle": title,
            },
            file,
        )
    print("Requested Dokploy deployment completed; remote application readiness still required")


if __name__ == "__main__":
    try:
        deploy()
    except (
        KeyError,
        ValueError,
        urllib.error.URLError,
        RuntimeError,
        subprocess.CalledProcessError,
    ):
        print("Deploy failed: verify configuration, transport and API contract", file=sys.stderr)
        sys.exit(1)
