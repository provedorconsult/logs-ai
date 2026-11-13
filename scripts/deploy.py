"""Trigger the configured Dokploy Compose resource without logging credentials."""

import json
import os
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
        if not (
            url.scheme == "http"
            and url.hostname in {"127.0.0.1", "localhost", "::1"}
            and os.environ.get("DOKPLOY_SSH_TUNNEL_VERIFIED") == "true"
        ):
            raise ValueError("Use validated HTTPS or an explicitly verified local SSH tunnel")
    if not url.hostname or url.path not in {"", "/"}:
        raise ValueError("Configure the administrative origin only")
    return value.rstrip("/")


def deploy():
    base = validate_url(os.environ["DOKPLOY_URL"])
    token = os.environ["DOKPLOY_API_TOKEN"]
    compose_id = os.environ["DOKPLOY_COMPOSE_ID"]
    if not token or not compose_id or compose_id.startswith("substitua_"):
        raise ValueError("Configure token and Compose resource")
    if os.environ.get("DOKPLOY_API_CONTRACT_VERIFIED") != "true":
        raise ValueError("Verify compose.deploy contract against this Dokploy instance first")
    request = urllib.request.Request(
        base + "/api/compose.deploy",
        data=json.dumps({"composeId": compose_id}).encode(),
        headers={"Content-Type": "application/json", "x-api-key": token},
        method="POST",
    )
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=30) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError("Deployment request rejected")
    print("Dokploy accepted deployment request; remote readiness still needs verification")


if __name__ == "__main__":
    try:
        deploy()
    except (KeyError, ValueError, urllib.error.URLError, RuntimeError):
        print("Deploy failed: verify configuration, transport and API contract", file=sys.stderr)
        sys.exit(1)
