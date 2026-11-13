"""Bounded post-deploy readiness polling with no sensitive response output."""

import json
import os
import time
import urllib.error
import urllib.request


def main():
    url = os.environ["APP_TEST_URL"].rstrip("/") + "/health"
    for _ in range(30):
        try:
            with urllib.request.urlopen(url, timeout=4) as response:
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
