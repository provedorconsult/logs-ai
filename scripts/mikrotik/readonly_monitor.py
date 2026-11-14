"""Fixed read-only RouterOS queries, with host-key validation before password authentication.

Dependency: paramiko==4.0.0 in an isolated tools environment, not the application image.
Credentials come only from mikrotik_username/mikrotik_password environment variables.
"""

import base64
import hashlib
import json
import os
import re
import socket


def fingerprint(key):
    return "SHA256:" + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")


def authenticate(transport, expected, username, password):
    if not expected or fingerprint(transport.get_remote_server_key()) != expected:
        raise ValueError("MikroTik host key does not match the independently approved fingerprint")
    transport.auth_password(username, password, fallback=False)


def query(transport, command):
    channel = transport.open_session(timeout=10)
    channel.settimeout(15)
    try:
        channel.exec_command(command)
        raw = channel.makefile("rb").read(65536)
        if len(raw) == 65536:
            raise RuntimeError("Read-only RouterOS query exceeded the output limit")
        output = raw.decode("utf-8", errors="replace")
        if channel.recv_exit_status() != 0:
            raise RuntimeError("Read-only RouterOS query failed")
        return output
    finally:
        channel.close()


def inspect(transport):
    resource = query(transport, "/system resource print without-paging")
    logging = query(transport, "/system logging action print detail without-paging")
    rules = query(transport, "/system logging print detail without-paging")
    clock = query(transport, "/system clock print without-paging")
    active = query(transport, "/ppp active print count-only where service=pppoe")
    secrets = query(transport, "/ppp secret print count-only")
    version = re.search(r"\bversion:\s*(\S+)", resource)
    zone = re.search(r"time-zone-name:\s*(\S+)", clock)
    return {
        "routerosVersion": version[1] if version else "unknown",
        "timeZone": zone[1] if zone else "unknown",
        "pppoeActiveCount": int(active.strip()) if active.strip().isdigit() else None,
        "localPppUserCount": int(secrets.strip()) if secrets.strip().isdigit() else None,
        "tcpLoggingPropertyPresent": "remote-protocol=" in logging,
        "cefLoggingPropertyPresent": "remote-log-format=" in logging,
        "logsAiActionPresent": 'name="logsaiPrivate"' in logging
        or "name=logsaiPrivate " in logging,
        "logsAiPppRulePresent": "logs-ai-ppp:" in rules,
        "logsAiAdminRulePresent": "logs-ai-admin:" in rules,
    }


def main():
    import paramiko

    expected = os.environ.get("MIKROTIK_HOST_FINGERPRINT", "")
    if not expected:
        raise ValueError("Provide an independently verified MikroTik host fingerprint")
    sock = socket.create_connection(
        (
            os.environ.get("MIKROTIK_PRIVATE_HOST", "192.168.15.1"),
            int(os.environ.get("MIKROTIK_PRIVATE_SSH_PORT", "2233")),
        ),
        timeout=10,
    )
    transport = paramiko.Transport(sock)
    try:
        transport.start_client(timeout=10)
        authenticate(
            transport, expected, os.environ["mikrotik_username"], os.environ["mikrotik_password"]
        )
        print(json.dumps(inspect(transport)))
    finally:
        transport.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Read-only router inspection failed; check host identity, access and permissions"
        ) from None
