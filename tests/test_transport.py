import importlib.util
import json
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
def listener(status=200, location=None):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append((self.path, self.headers.get("x-api-key")))
            self.send_response(status)
            if location:
                self.send_header("Location", location)
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())

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
