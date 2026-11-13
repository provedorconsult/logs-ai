"""Bounded post-deploy readiness polling with no sensitive response output."""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from transport import approved_opener


def require_deployment_receipt():
    path = os.environ.get("DOKPLOY_DEPLOYMENT_RECEIPT")
    if not path and os.environ.get("DOKPLOY_COMPOSE_ID"):
        path = "work/dokploy-deployment.json"
    if path:
        with Path(path).open() as file:
            receipt = json.load(file)
        if (
            receipt.get("status") != "done"
            or not receipt.get("deploymentId")
            or not receipt.get("requestTitle")
            or not os.environ.get("EXPECTED_REVISION")
            or receipt.get("revision") != os.environ["EXPECTED_REVISION"]
            or not os.environ.get("DOKPLOY_COMPOSE_ID")
            or receipt.get("composeId") != os.environ["DOKPLOY_COMPOSE_ID"]
        ):
            raise ValueError("A completed deployment receipt matching this release is required")


def main():
    require_deployment_receipt()
    base = os.environ["APP_TEST_URL"]
    parsed = urllib.parse.urlsplit(base)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("APP_TEST_URL must be the exact application origin without credentials")
    url = base.rstrip("/") + "/health"
    opener = approved_opener()
    for _ in range(30):
        try:
            with opener.open(url, timeout=4) as response:
                expected = os.environ.get("EXPECTED_REVISION")
                revision_matches = (
                    not expected or response.headers.get("X-App-Revision") == expected
                )
                if (
                    revision_matches
                    and response.status == 200
                    and json.load(response)
                    == {
                        "status": "ok",
                        "database": "ok",
                    }
                ):
                    print("Application and database readiness: PASS")
                    return
        except (urllib.error.URLError, ValueError, TimeoutError):
            pass
        time.sleep(2)
    raise SystemExit("Application readiness did not become healthy")


if __name__ == "__main__":
    main()
