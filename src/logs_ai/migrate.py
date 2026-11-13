"""Transactional forward migrations, serialized across replicas and checksum protected."""

import hashlib
import os
from pathlib import Path

from logs_ai.db import connect


def migrate(directory: Path | None = None):
    root = directory or Path(os.environ.get("MIGRATIONS_DIR", "migrations"))
    files = sorted(root.glob("[0-9]*.sql"))
    if not files:
        raise RuntimeError("No migrations found")
    with connect() as conn:
        # Transaction-scoped lock prevents racing first starts on Swarm.
        conn.execute("SELECT pg_advisory_xact_lock(74329102)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version text PRIMARY KEY, checksum text NOT NULL, "
            "applied_at timestamptz NOT NULL DEFAULT now())"
        )
        applied = dict(conn.execute("SELECT version, checksum FROM schema_migrations").fetchall())
        known = {file.name for file in files}
        if set(applied) - known:
            raise RuntimeError("Database schema is newer than this release")
        for file in files:
            sql = file.read_bytes()
            checksum = hashlib.sha256(sql).hexdigest()
            if file.name in applied:
                if applied[file.name] != checksum:
                    raise RuntimeError("Applied migration checksum mismatch")
                continue
            conn.execute(sql.decode("utf-8"))
            conn.execute(
                "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                (file.name, checksum),
            )


def main():
    try:
        migrate()
    except Exception:
        raise SystemExit(
            "Migration failed; check database configuration and migration integrity"
        ) from None
    print("Migrations applied successfully")


if __name__ == "__main__":
    main()
