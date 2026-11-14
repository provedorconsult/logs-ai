import hashlib
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


def metadata():
    return psycopg.connect(
        os.environ["WEB_DATABASE_URL"],
        connect_timeout=5,
        row_factory=dict_row,
        options="-c statement_timeout=10000 -c timezone=UTC",
    )


def logs():
    conn = psycopg.connect(
        os.environ["LOG_DATABASE_URL"],
        connect_timeout=5,
        row_factory=dict_row,
        options="-c statement_timeout=10000 -c default_transaction_read_only=on -c timezone=UTC",
    )
    conn.execute("SET TRANSACTION READ ONLY")
    return conn


def migrate():
    directory = Path(os.environ.get("WEB_MIGRATIONS_DIR", "web_migrations"))
    files = sorted(directory.glob("[0-9]*.sql"))
    if not files:
        raise RuntimeError("Web migrations unavailable")
    with metadata() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(74329103)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS web_schema_migrations(version t"
            "ext PRIMARY KEY, checksum text NOT NULL)"
        )
        applied = {
            r["version"]: r["checksum"] for r in conn.execute("SELECT * FROM web_schema_migrations")
        }
        if set(applied) - {f.name for f in files}:
            raise RuntimeError("Web database newer than application")
        for file in files:
            checksum = hashlib.sha256(file.read_bytes()).hexdigest()
            if file.name in applied:
                if applied[file.name] != checksum:
                    raise RuntimeError("Web migration checksum mismatch")
            else:
                conn.execute(file.read_text())
                conn.execute(
                    "INSERT INTO web_schema_migrations VALUES (%s,%s)", (file.name, checksum)
                )


def audit(conn, user_id, action, target_id=None):
    conn.execute(
        "INSERT INTO web_audit_log(user_id,action,target_id) VALUES (%s,%s,%s)",
        (user_id, action, target_id),
    )
