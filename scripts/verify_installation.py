"""Verify readiness and newly committed events for every configured MikroTik."""

import argparse
import hashlib
import json
import re
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path

from prepare_installation import EVENTS, address, slug, write_private
from transport import approved_opener


def origin(value):
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("Configure an exact application origin without credentials")
    return value.rstrip("/")


def manifest_identity(manifest):
    if manifest.get("format") != 1 or not re.fullmatch(
        r"[0-9a-f]{40}", manifest.get("revision", "")
    ):
        raise ValueError("Unsupported manifest or revision")
    slug(manifest["instance"])
    for field in ("core_url", "collector_url"):
        origin(manifest[field])
    routers = manifest["routers"]
    if not isinstance(routers, list) or not 1 <= len(routers) <= 32:
        raise ValueError("Invalid manifest routers")
    for router in routers:
        slug(router["id"])
        address(router["source_ip"])
    if len({r["id"] for r in routers}) != len(routers) or len(
        {r["source_ip"] for r in routers}
    ) != len(routers):
        raise ValueError("Duplicate manifest routers")
    kinds = manifest["required_event_kinds"]
    if not kinds or not isinstance(kinds, list) or any(k not in EVENTS for k in kinds):
        raise ValueError("Invalid commissioning event kinds")
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()


def get_json(opener, url):
    with opener.open(url, timeout=10) as response:
        body = response.read(65537)
        if response.status != 200 or len(body) > 65536:
            raise ValueError("Unexpected HTTP response")
        return json.loads(body), response.headers.get("X-App-Revision")


def capture(manifest):
    identity = manifest_identity(manifest)
    opener = approved_opener()
    for field in ("core_url", "collector_url"):
        body, revision = get_json(opener, origin(manifest[field]) + "/health")
        if body != {"status": "ok", "database": "ok"} or revision != manifest["revision"]:
            raise ValueError("Readiness or deployed revision mismatch")
    metrics, _ = get_json(opener, origin(manifest["collector_url"]) + "/metrics")
    if metrics.get("revision") != manifest["revision"] or not re.fullmatch(
        r"[0-9a-f]{32}", metrics.get("instance_id", "")
    ):
        raise ValueError("Collector metrics revision/instance is missing or mismatched")
    counts = metrics.get("persisted_by_source_kind", {})
    if set(counts) != {r["source_ip"] for r in manifest["routers"]}:
        raise ValueError("Collector configured sources differ from manifest")
    for values in counts.values():
        if not isinstance(values, dict) or any(
            type(v) is not int or v < 0 for v in values.values()
        ):
            raise ValueError("Invalid commit counters")
    if metrics.get("queued") != 0:
        raise ValueError("Wait until the persistence queue is drained")
    return {
        "manifest_sha256": identity,
        "revision": manifest["revision"],
        "instance_id": metrics["instance_id"],
        "captured_at": datetime.now(UTC).isoformat(),
        "counts": counts,
        "counters": {
            key: metrics.get(key)
            for key in (
                "received",
                "persisted",
                "ignored",
                "rejected",
                "db_errors",
                "queued",
                "connections",
            )
        },
    }


def compare(manifest, baseline, current):
    identity = manifest_identity(manifest)
    for sample in (baseline, current):
        counts = sample.get("counts", {})
        if set(counts) != {r["source_ip"] for r in manifest["routers"]}:
            raise ValueError("Snapshot sources mismatch")
        for values in counts.values():
            if not isinstance(values, dict) or any(
                type(v) is not int or v < 0 for v in values.values()
            ):
                raise ValueError("Invalid snapshot counters")
        if not re.fullmatch(r"[0-9a-f]{32}", sample.get("instance_id", "")):
            raise ValueError("Invalid process identity")
        if (
            sample.get("manifest_sha256") != identity
            or sample.get("revision") != manifest["revision"]
        ):
            raise ValueError("Baseline/manifest/revision mismatch")
    if baseline.get("instance_id") != current.get("instance_id"):
        raise ValueError("Collector restarted; take a new baseline and repeat the events")
    results = []
    for router in manifest["routers"]:
        source = router["source_ip"]
        before = baseline["counts"][source]
        after = current["counts"][source]
        if any(after.get(k, 0) < v for k, v in before.items()):
            raise ValueError("Commit counters regressed")
        for kind in manifest["required_event_kinds"]:
            delta = after.get(kind, 0) - before.get(kind, 0)
            results.append(
                {"router": router["id"], "kind": kind, "new_events": delta, "pass": delta > 0}
            )
    return {
        "status": "PASS" if all(r["pass"] for r in results) else "FAIL",
        "revision": manifest["revision"],
        "manifest_sha256": identity,
        "checks": results,
        "snapshot": current,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("baseline", "verify"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text())
        sample = capture(manifest)
        if args.operation == "baseline":
            result = sample
        else:
            if not args.baseline:
                raise ValueError("Provide a commissioning baseline")
            result = compare(manifest, json.loads(args.baseline.read_text()), sample)
        write_private(args.output, json.dumps(result, indent=2) + "\n")
    except (ValueError, OSError, KeyError, TypeError):
        raise SystemExit(
            "Verification failed: check transport, health, revision, sources and baseline; "
            "no acceptance issued"
        ) from None
    if args.operation == "verify" and result["status"] != "PASS":
        raise SystemExit("Required new events are missing; see the private receipt")
    print(
        "Readiness baseline saved"
        if args.operation == "baseline"
        else "New committed events verified for every required router/kind"
    )


if __name__ == "__main__":
    main()
