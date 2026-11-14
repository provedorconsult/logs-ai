"""Fail before destructive integration fixtures unless the target is explicitly disposable."""

import os

import psycopg
from psycopg.conninfo import conninfo_to_dict


def validate_test_database(url):
    if any(name.startswith("PG") for name in os.environ):
        raise ValueError("Remove inherited PG parameters before disposable database tests")
    if os.environ.get("TEST_DATABASE_DISPOSABLE") != "true":
        raise ValueError("Explicit TEST_DATABASE_DISPOSABLE=true is required")
    params = conninfo_to_dict(url)
    if (
        set(params) - {"host", "port", "user", "password", "dbname"}
        or params.get("host") not in {"127.0.0.1", "::1"}
        or params.get("dbname") != "logs_ai_ci"
        or params.get("user") != "logs_ai"
        or not params.get("port")
        or params.get("port") != os.environ.get("TEST_DATABASE_EXPECTED_PORT")
    ):
        raise ValueError("Use the explicitly selected local disposable logs_ai_ci database")
    return params


def connect_test_database(url):
    params = validate_test_database(url)
    # Pin the numeric transport address even if the process environment changes.
    conn = psycopg.connect(url, hostaddr=params["host"], connect_timeout=3)
    info = conn.info
    if (
        info.hostaddr != params["host"]
        or info.host != params["host"]
        or str(info.port) != params["port"]
        or info.dbname != params["dbname"]
        or info.user != params["user"]
    ):
        conn.close()
        raise ValueError("Effective database destination does not match the disposable target")
    return conn
