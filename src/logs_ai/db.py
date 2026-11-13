"""Short-lived database connections; credentials never enter application logs."""

import os

import psycopg


def connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL must be configured")
    return psycopg.connect(url, connect_timeout=3, options="-c statement_timeout=3000")
