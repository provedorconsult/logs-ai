import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("deploy", Path("scripts/deploy.py"))
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


@pytest.mark.parametrize(
    "url",
    [
        "http://100.80.0.1:3000",
        "https://token:secret@example.com",
        "https://example.com?token=secret",
        "https://example.com/path",
        "file:///tmp/token",
    ],
)
def test_unsafe_administrative_url_is_rejected(url):
    with pytest.raises(ValueError):
        deploy.validate_url(url)


def test_tunnel_requires_explicit_validation(monkeypatch):
    monkeypatch.delenv("DOKPLOY_SSH_TUNNEL_VERIFIED", raising=False)
    with pytest.raises(ValueError):
        deploy.validate_url("http://127.0.0.1:13000")
    monkeypatch.setenv("DOKPLOY_SSH_TUNNEL_VERIFIED", "true")
    assert deploy.validate_url("http://127.0.0.1:13000") == "http://127.0.0.1:13000"


def test_https_origin_is_accepted():
    assert deploy.validate_url("https://dokploy.example.com/") == "https://dokploy.example.com"


def test_redirect_is_rejected():
    assert deploy.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other") is None
