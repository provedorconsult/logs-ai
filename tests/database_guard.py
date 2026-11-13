"""Fail before destructive integration fixtures unless the target is explicitly disposable."""

import os

from psycopg.conninfo import conninfo_to_dict


def validate_test_database(url):
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
