import importlib.util
import json
import subprocess
import threading
import urllib.error
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("transport_deploy", Path("scripts/deploy.py"))
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


@contextmanager
def listener(status=200, location=None, body=None, revision=None):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append((self.path, self.headers.get("x-api-key")))
            self.send_response(status)
            if location:
                self.send_header("Location", location)
            if revision:
                self.send_header("X-App-Revision", revision)
            self.end_headers()
            self.wfile.write(json.dumps(body if body is not None else {"ok": True}).encode())

        def do_CONNECT(self):
            received.append((self.path, None))
            self.send_response(403)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_direct_transport_ignores_adversarial_inherited_proxy(monkeypatch):
    with listener() as (target, expected), listener() as (attacker, leaked):
        monkeypatch.setenv("http_proxy", attacker)
        monkeypatch.setenv("HTTP_PROXY", attacker)
        monkeypatch.setenv("no_proxy", "")
        monkeypatch.setenv("NO_PROXY", "")
        monkeypatch.setenv("DOKPLOY_TRANSPORT", "direct")
        deploy.api(target, "synthetic-key", "project.all")
        assert expected == [("/api/project.all", "synthetic-key")]
        assert leaked == []


def test_only_pinned_proxy_receives_token_even_with_inherited_bypass(monkeypatch):
    with listener() as (approved, expected), listener() as (attacker, leaked):
        monkeypatch.setenv("http_proxy", attacker)
        monkeypatch.setenv("HTTP_PROXY", attacker)
        monkeypatch.setenv("no_proxy", "*")
        monkeypatch.setenv("NO_PROXY", "*")
        monkeypatch.setenv("DOKPLOY_TRANSPORT", "proxy")
        monkeypatch.setenv("DOKPLOY_APPROVED_PROXY", approved)
        deploy.api("http://service.example.ts.net:3000", "synthetic-key", "project.all")
        assert expected == [("http://service.example.ts.net:3000/api/project.all", "synthetic-key")]
        assert leaked == []


def test_no_implicit_transport_can_send_a_token(monkeypatch):
    with listener() as (attacker, leaked):
        monkeypatch.setenv("http_proxy", attacker)
        monkeypatch.delenv("DOKPLOY_TRANSPORT", raising=False)
        with pytest.raises(ValueError):
            deploy.api("http://service.example.ts.net:3000", "synthetic-key", "project.all")
        assert leaked == []


def test_redirect_never_forwards_token_to_another_origin(monkeypatch):
    monkeypatch.setenv("DOKPLOY_TRANSPORT", "direct")
    with listener() as (attacker, leaked), listener(302, attacker) as (target, expected):
        with pytest.raises(urllib.error.HTTPError):
            deploy.api(target, "synthetic-key", "project.all")
        assert len(expected) == 1
        assert leaked == []


def test_git_direct_transport_does_not_connect_to_inherited_proxy(monkeypatch):
    monkeypatch.setenv("DOKPLOY_TRANSPORT", "direct")
    with listener() as (attacker, leaked), socket_target() as target:
        monkeypatch.setenv("https_proxy", attacker)
        monkeypatch.setenv("HTTPS_PROXY", attacker)
        command, env = deploy.git_transport()
        result = subprocess.run(
            [*command, "ls-remote", target], env=env, capture_output=True, timeout=5
        )
        assert result.returncode != 0
        assert leaked == []


@contextmanager
def socket_target():
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        # Reserved but not listening: direct Git fails locally without external access.
        yield f"https://127.0.0.1:{sock.getsockname()[1]}/synthetic.git"


def test_git_proxy_transport_uses_only_pinned_proxy(monkeypatch):
    monkeypatch.setenv("DOKPLOY_TRANSPORT", "proxy")
    with (
        listener() as (approved, received),
        listener() as (attacker, leaked),
        socket_target() as target,
    ):
        monkeypatch.setenv("https_proxy", attacker)
        monkeypatch.setenv("HTTPS_PROXY", attacker)
        monkeypatch.setenv("NO_PROXY", "*")
        monkeypatch.setenv("DOKPLOY_APPROVED_PROXY", approved)
        command, env = deploy.git_transport()
        subprocess.run([*command, "ls-remote", target], env=env, capture_output=True, timeout=5)
        assert len(received) == 1
        assert leaked == []
