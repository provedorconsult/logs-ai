"""Trigger the configured Dokploy Compose resource without logging credentials."""

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from transport import NoRedirect as NoRedirect
from transport import approved_opener, approved_proxy

GIT_ORIGIN = "https://github.com/provedorconsult/logs-ai.git"


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


def parse_environment(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Compose environment is missing or redacted")
    fields = {}
    for line in value.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, content = line.partition("=")
        if (
            not separator
            or not re.fullmatch(r"[A-Z_][A-Z_0-9]*", key)
            or key in fields
            or content.startswith(("'", '"'))
            or re.fullmatch(r"\*{3,}|\[?redacted\]?|<redacted>|changeme", content, re.I)
        ):
            raise ValueError("Environment contains ambiguous or redacted fields")
        fields[key] = content
    required = {"POSTGRES_PASSWORD", "APP_BIND_HOST", "APP_PORT", "APP_REVISION", "APP_IMAGE"}
    if any(not fields.get(key) for key in required):
        raise ValueError("Environment lacks required Compose fields")
    if not re.fullmatch(r"[0-9a-fA-F]{32,128}", fields["POSTGRES_PASSWORD"]):
        raise ValueError("Compose requires a configured hexadecimal PostgreSQL secret")
    return fields


def revision_environment(value, revision):
    path = os.environ.get("DOKPLOY_ENV_FILE")
    if not path:
        raise ValueError("An authoritative protected Compose environment file is required")
    with open(path, encoding="utf-8") as file:
        metadata = os.fstat(file.fileno())
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_mode & 0o077
            or metadata.st_uid != os.getuid()
        ):
            raise ValueError("Authoritative environment must be owned by this user and mode 0600")
        snapshot = file.read()
    expected = parse_environment(snapshot)
    actual = parse_environment(value)
    mutable = {"APP_REVISION", "APP_IMAGE"}
    if actual.keys() != expected.keys() or any(
        actual[key] != expected[key] for key in expected.keys() - mutable
    ):
        raise ValueError("Compose environment does not match the complete authoritative snapshot")
    lines = [line for line in snapshot.splitlines() if line.partition("=")[0] not in mutable]
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


def ref_pattern_matches(pattern, ref):
    if pattern == "~ALL":
        return True
    if (
        not isinstance(pattern, str)
        or not pattern.startswith("refs/")
        or "**" in pattern
        or any(char in pattern for char in "?[]{}\\")
    ):
        raise ValueError("Unsupported ruleset pattern; exact or component-local star is required")
    # GitHub uses FNM_PATHNAME: a single star must never cross a slash.
    regex = re.escape(pattern).replace(r"\*", "[^/]*")
    return re.fullmatch(regex, ref) is not None


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
        includes, excludes = names.get("include"), names.get("exclude")
        if not isinstance(includes, list) or not isinstance(excludes, list):
            raise ValueError("Ruleset coverage response is incomplete")
        included = [ref_pattern_matches(p, ref) for p in includes]
        excluded = [ref_pattern_matches(p, ref) for p in excludes]
        if any(included) and not any(excluded):
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
            identity_matches = (
                record.get("deploymentId") == returned_id
                if returned_id is not None
                else record.get("title") == title
            )
            if record.get("composeId") != compose_id or not identity_matches:
                raise ValueError("New deployment does not match this request")
            if record.get("status") == "done":
                return record
            if record.get("status") not in {"queued", "running"}:
                raise RuntimeError("Requested deployment did not complete successfully")
        time.sleep(2)
    raise RuntimeError("Requested deployment timed out")


def require_git_tls_environment():
    if "GIT_SSL_NO_VERIFY" in os.environ:
        raise ValueError("Inherited GIT_SSL_NO_VERIFY is forbidden")


def git_transport(url=GIT_ORIGIN):
    require_git_tls_environment()
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Git transport requires an HTTPS origin without credentials")
    proxy = approved_proxy() or ""
    env = {
        key: value
        for key, value in os.environ.items()
        if key.lower() not in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}
    }
    env["GIT_TERMINAL_PROMPT"] = "0"
    command = [
        "git",
        "-c",
        f"http.proxy={proxy}",
        "-c",
        f"http.https://github.com.proxy={proxy}",
        "-c",
        f"remote.origin.proxy={proxy}",
        "-c",
        "http.followRedirects=false",
        "-c",
        "http.sslVerify=true",
        "-c",
        "http.https://github.com.sslVerify=true",
    ]
    for key, expected in [
        ("http.proxy", proxy),
        ("http.followRedirects", "false"),
        ("http.sslVerify", "true"),
    ]:
        actual = subprocess.check_output(
            [
                *command,
                "config",
                *([] if key == "http.proxy" else ["--type=bool"]),
                "--get-urlmatch",
                key,
                url,
            ],
            env=env,
            text=True,
        ).strip()
        if actual != expected:
            raise ValueError("Git URL-specific configuration conflicts with approved transport")
    return command, env


def deployment_ref(revision, allow_create):
    require_git_tls_environment()
    if subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() != revision:
        raise ValueError("Local checkout does not match EXPECTED_REVISION")
    for push in [False, True]:
        urls = subprocess.check_output(
            ["git", "remote", "get-url", "--all", *(["--push"] if push else []), "origin"],
            text=True,
        ).splitlines()
        if urls != [GIT_ORIGIN]:
            raise ValueError("Fetch and push must use the single canonical logs-ai .git URL")
    command, env = git_transport(GIT_ORIGIN)
    tag = f"logs-ai-deploy-{revision}"
    ref = f"refs/tags/{tag}"
    existing = subprocess.check_output(
        [*command, "ls-remote", "origin", ref], env=env, text=True, timeout=30
    ).strip()
    if existing:
        if existing.split()[0] != revision:
            raise ValueError("Deployment ref already points to a different commit")
    else:
        if not allow_create:
            raise ValueError("Deployment ref disappeared; verification must not recreate it")
        # Never overwrite a deployment ref, including on retry.
        subprocess.run(
            [*command, "push", "origin", f"{revision}:{ref}"],
            env=env,
            check=True,
            capture_output=True,
            timeout=30,
        )
    return tag


def publish_deployment_ref(revision):
    return deployment_ref(revision, allow_create=True)


def verify_deployment_ref(revision):
    return deployment_ref(revision, allow_create=False)


def recovery_path():
    value = os.environ.get("DOKPLOY_RECOVERY_FILE", "work/dokploy-recovery.json")
    if not value:
        raise ValueError("Configure a durable protected recovery file outside runner cleanup paths")
    path = Path(value)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        roots = [os.environ.get("GITHUB_WORKSPACE"), os.environ.get("RUNNER_TEMP")]
        if not path.is_absolute() or any(
            root and path.resolve().is_relative_to(Path(root).resolve()) for root in roots
        ):
            raise ValueError("Runner recovery file must survive checkout and temporary cleanup")
    return path


def read_recovery(path):
    if path.is_symlink():
        raise ValueError("Recovery file must not be a symlink")
    with path.open() as file:
        info = os.fstat(file.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
            raise ValueError("Recovery file must be private and owned by this user")
        return json.load(file)


def write_recovery(path, record, create=False):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if create:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as file:
            json.dump(record, file)
        return
    if read_recovery(path)["journalId"] != record["journalId"]:
        raise ValueError("Recovery ownership changed")
    fd, temporary = tempfile.mkstemp(prefix=".dokploy-recovery-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as file:
            json.dump(record, file)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def remove_recovery(path, record):
    if read_recovery(path)["journalId"] != record["journalId"]:
        raise ValueError("Recovery ownership changed")
    path.unlink()


def scope_bindings(compose):
    return {
        key: compose.get(key)
        for key in (
            "environmentId",
            "sourceType",
            "owner",
            "repository",
            "githubId",
            "customGitUrl",
            "composeType",
            "composePath",
            "appName",
            "serverId",
            "autoDeploy",
        )
    }


def reconcile():
    path = recovery_path()
    record = read_recovery(path)
    source_type = record["scope"].get("sourceType")
    branch_field = "branch" if source_type == "github" else "customGitBranch"
    allowed = {branch_field, "command", "env"}
    if source_type not in {"git", "github"} or any(
        set(record[state]) != allowed
        or any(not isinstance(value, str) for value in record[state].values())
        for state in ["before", "planned"]
    ):
        raise ValueError("Recovery record contains unsupported configuration fields")
    base = validate_url(os.environ["DOKPLOY_URL"])
    compose_id = os.environ["DOKPLOY_COMPOSE_ID"]
    project_id = os.environ["DOKPLOY_PROJECT_ID"]
    if (
        record["base"] != base
        or record["composeId"] != compose_id
        or record["projectId"] != project_id
        or record["phase"] != "prepared"
        or os.environ.get("DOKPLOY_API_CONTRACT_VERIFIED") != "true"
    ):
        raise ValueError("Recovery requires the same scope and no deployment request")
    token = os.environ.get("DOKPLOY_API_TOKEN") or os.environ["dokploy_token"]

    def inspect():
        current = api(base, token, "compose.one", query={"composeId": compose_id})
        deployments = api(base, token, "deployment.allByCompose", query={"composeId": compose_id})
        if (
            current.get("environment", {}).get("projectId") != project_id
            or scope_bindings(current) != record["scope"]
            or {d["deploymentId"] for d in deployments} != set(record["deploymentIdsBefore"])
            or any(d.get("status") not in {"done", "error"} for d in deployments)
            or any(
                current.get(key) not in [value, record["planned"][key]]
                for key, value in record["before"].items()
            )
        ):
            raise ValueError(
                "External change or deployment prevents automatic configuration recovery"
            )
        return current

    current = inspect()
    if current.get("env") != record["before"]["env"]:
        api(
            base,
            token,
            "compose.saveEnvironment",
            {"composeId": compose_id, "env": record["before"]["env"]},
        )
    metadata = {
        key: value
        for key, value in record["before"].items()
        if key != "env" and current.get(key) != value
    }
    if metadata:
        api(base, token, "compose.update", {"composeId": compose_id, **metadata})
    current = inspect()
    if any(current.get(key) != value for key, value in record["before"].items()):
        raise RuntimeError("Configuration recovery has not been confirmed")
    remove_recovery(path, record)
    print("Previous Compose configuration restored; no application or database rollback performed")


def deploy():
    receipt = Path(os.environ.get("DOKPLOY_DEPLOYMENT_RECEIPT", "work/dokploy-deployment.json"))
    receipt.unlink(missing_ok=True)
    recovery = recovery_path()
    if recovery.exists() or recovery.is_symlink():
        raise ValueError("Resolve the existing recovery record before another deployment")
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
    journal = {
        "journalId": uuid.uuid4().hex,
        "phase": "prepared",
        "base": base,
        "composeId": compose_id,
        "projectId": project_id,
        "scope": scope_bindings(compose),
        "deploymentIdsBefore": sorted(previous_ids),
        "before": {
            branch_field: branch,
            "command": compose.get("command", ""),
            "env": compose["env"],
        },
        "planned": {branch_field: tag, "command": "", "env": environment},
    }
    write_recovery(recovery, journal, create=True)
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
    # Persist BEFORE submitting, because a transport failure may hide an accepted request.
    journal["phase"] = "deployment_requested"
    write_recovery(recovery, journal)
    result = api(base, token, "compose.deploy", {"composeId": compose_id, "title": title})
    record = wait_deployment(base, token, compose_id, previous_ids, title, result)
    require_immutable_tag(tag)
    verify_deployment_ref(revision)
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
    remove_recovery(recovery, journal)
    print("Requested Dokploy deployment completed; remote application readiness still required")


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--reconcile"]:
            reconcile()
        elif sys.argv[1:]:
            raise ValueError("Use no arguments or --reconcile")
        else:
            deploy()
    except (
        KeyError,
        ValueError,
        urllib.error.URLError,
        RuntimeError,
        subprocess.SubprocessError,
    ):
        print("Deploy failed: verify configuration, transport and API contract", file=sys.stderr)
        sys.exit(1)
