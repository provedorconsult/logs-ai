"""Bounded, fail-closed source registry; access is restricted to a database view."""

import ipaddress
import threading
import time

import psycopg


class ClientRegistry:
    def __init__(self, url, ttl=3):
        self.url, self.ttl = url, ttl
        self._sources, self._expires, self._lock = set(), 0, threading.Lock()

    def sources(self):
        with self._lock:
            if time.monotonic() < self._expires:
                return set(self._sources)
            with psycopg.connect(
                self.url,
                connect_timeout=4,
                options="-c default_transaction_read_only=on -c statement_timeout=4000",
            ) as conn:
                rows = conn.execute(
                    "SELECT source_ip FROM web_client_sources WHERE enabled LIMIT 33"
                ).fetchall()
            if len(rows) > 32:
                raise RuntimeError("Registry source limit exceeded")
            sources = {ipaddress.ip_address(row[0]) for row in rows}
            self._sources, self._expires = sources, time.monotonic() + self.ttl
            return set(sources)
