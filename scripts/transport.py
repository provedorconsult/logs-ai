"""Explicit shared HTTP transport for administrative requests and readiness."""

import os
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PinnedProxy(urllib.request.ProxyHandler):
    def proxy_open(self, req, proxy, type):
        # Proxy selection is explicit; inherited NO_PROXY must not change it.
        req.set_proxy(urllib.parse.urlsplit(proxy).netloc, "http")
        return None


def approved_proxy():
    mode = os.environ.get("DOKPLOY_TRANSPORT")
    if mode == "direct":
        return None
    elif mode == "proxy":
        proxy = os.environ.get("DOKPLOY_APPROVED_PROXY", "")
        parsed = urllib.parse.urlsplit(proxy)
        if (
            parsed.scheme != "http"
            or not parsed.hostname
            or not parsed.port
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Configure the exact approved HTTP proxy origin")
        return proxy
    else:
        raise ValueError("Explicitly select direct or approved proxy transport")


def approved_opener():
    proxy = approved_proxy()
    handler = (
        PinnedProxy({"http": proxy, "https": proxy}) if proxy else urllib.request.ProxyHandler({})
    )
    return urllib.request.build_opener(handler, NoRedirect())
