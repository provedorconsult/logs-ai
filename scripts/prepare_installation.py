"""Render a private, new-server installation bundle without contacting any host."""

import argparse
import hashlib
import ipaddress
import json
import os
import re
import secrets
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = tuple(ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
TAILNET = ipaddress.ip_network("100.64.0.0/10")
EVENTS = {
    "pppoe.authenticated",
    "pppoe.session.started",
    "pppoe.session.ended",
    *{"ppp.user." + s for s in ("created", "updated", "deleted", "enabled", "disabled")},
    *{"routeros.admin_user." + s for s in ("created", "updated", "deleted", "enabled", "disabled")},
    "routeros.admin.login",
    "routeros.admin.logout",
}


def keys(value, required, optional=()):
    if (
        not isinstance(value, dict)
        or not set(required) <= value.keys()
        or value.keys() - set(required) - set(optional)
    ):
        raise ValueError("Profile contains missing or unknown fields")


def address(value, health=False):
    if not isinstance(value, str):
        raise ValueError("IPv4 addresses must be strings")
    ip = ipaddress.IPv4Address(value)
    if not (
        any(ip in network for network in PRIVATE) or (health and (ip.is_loopback or ip in TAILNET))
    ):
        raise ValueError(
            "Configure an explicit private IPv4 address; health also accepts loopback/Tailnet"
        )
    return str(ip)


def slug(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", value):
        raise ValueError("Instance/router ID must be a lowercase slug, maximum 32 characters")
    return value


def validate(profile):
    keys(profile, {"instance", "server", "routers", "required_event_kinds"})
    slug(profile["instance"])
    server = profile["server"]
    keys(server, {"private_ip", "syslog_port", "health_bind", "core_port", "collector_port"})
    address(server["private_ip"])
    address(server["health_bind"], health=True)
    ports = [server[key] for key in ("syslog_port", "core_port", "collector_port")]
    if (
        any(type(port) is not int or not 1 <= port <= 65535 for port in ports)
        or len(set(ports)) != 3
    ):
        raise ValueError("Configure three distinct TCP ports between 1 and 65535")
    routers = profile["routers"]
    if not isinstance(routers, list) or not 1 <= len(routers) <= 32:
        raise ValueError("Configure one to 32 routers")
    ids, sources = set(), set()
    for router in routers:
        keys(router, {"id", "source_ip", "action_name"})
        ident, source = slug(router["id"]), address(router["source_ip"])
        if ident in ids or source in sources or source == server["private_ip"]:
            raise ValueError("Router IDs/sources must be unique and distinct from receiver")
        if not isinstance(router["action_name"], str) or not re.fullmatch(
            r"[A-Za-z0-9]{1,32}", router["action_name"]
        ):
            raise ValueError("RouterOS action names must contain only letters/numbers, maximum 32")
        ids.add(ident)
        sources.add(source)
    kinds = profile["required_event_kinds"]
    if (
        not isinstance(kinds, list)
        or not kinds
        or any(not isinstance(k, str) or k not in EVENTS for k in kinds)
        or len(set(kinds)) != len(kinds)
    ):
        raise ValueError("Configure distinct supported event kinds for commissioning")
    return profile


def render_router(template, server, router):
    values = {
        "destination": server["private_ip"],
        "source": router["source_ip"],
        "port": server["syslog_port"],
        "actionName": router["action_name"],
    }
    for key, value in values.items():
        literal = str(value) if type(value) is int else json.dumps(value)
        template, count = re.subn(rf"(?m)^:local {key} .*?$", f":local {key} {literal}", template)
        if count != 1:
            raise ValueError("RouterOS template configuration block is ambiguous")
    return template


def write_private(path, content):
    with open(path, "x", opener=lambda p, f: os.open(p, f, 0o600)) as file:
        file.write(content)


def prepare(profile, revision, output):
    validate(profile)
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("A full lowercase Git commit SHA is required")
    server = profile["server"]
    env = {
        "LOGS_AI_INSTANCE": profile["instance"],
        "APP_REVISION": revision,
        "POSTGRES_PASSWORD": secrets.token_hex(32),
        "RECEIVER_BIND": server["private_ip"],
        "SYSLOG_PORT": str(server["syslog_port"]),
        "HEALTH_BIND": server["health_bind"],
        "CORE_PORT": str(server["core_port"]),
        "COLLECTOR_PORT": str(server["collector_port"]),
        "MIKROTIK_ALLOWED_SOURCES": ",".join(r["source_ip"] for r in profile["routers"]),
    }
    manifest = {
        "format": 1,
        "revision": revision,
        "instance": profile["instance"],
        "profile_sha256": hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest(),
        "core_url": f"http://{server['health_bind']}:{server['core_port']}",
        "collector_url": f"http://{server['health_bind']}:{server['collector_port']}",
        "routers": [{"id": r["id"], "source_ip": r["source_ip"]} for r in profile["routers"]],
        "required_event_kinds": profile["required_event_kinds"],
    }
    output = Path(output)
    output.mkdir(mode=0o700)  # Exclusive: never regenerate credentials over an existing bundle.
    try:
        write_private(output / ".env", "".join(f"{key}={value}\n" for key, value in env.items()))
        write_private(
            output / "docker-compose.yml", (ROOT / "deploy/standalone.compose.yml").read_text()
        )
        write_private(output / "manifest.json", json.dumps(manifest, indent=2) + "\n")
        (output / "routers").mkdir(mode=0o700)
        for router in profile["routers"]:
            target = output / "routers" / router["id"]
            target.mkdir(mode=0o700)
            for name in ("install-logging.rsc", "remove-logging.rsc"):
                template = (ROOT / "scripts/mikrotik" / name).read_text()
                write_private(target / name, render_router(template, server, router))
    except Exception:
        shutil.rmtree(output)
        raise
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        prepare(json.loads(args.profile.read_text()), args.revision, args.output)
    except (ValueError, OSError):
        raise SystemExit(
            "Preparation failed: validate profile/revision and use a new output directory"
        ) from None
    print(
        "Installation bundle prepared; keep its .env private and do not regenerate it for upgrades"
    )


if __name__ == "__main__":
    main()
