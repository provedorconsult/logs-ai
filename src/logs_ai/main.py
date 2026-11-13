"""HTTP interface with active database readiness checks."""

import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from logs_ai.db import connect

app = FastAPI(title="logs-ai", docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
def health():
    try:
        with connect() as conn:
            # Check both connectivity and the schema required by this release.
            ready = conn.execute(
                "SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = %s) "
                "AND to_regclass('public.log_events') IS NOT NULL",
                ("001_initial.sql",),
            ).fetchone()[0]
        if not ready:
            raise RuntimeError("Schema not ready")
    except Exception:
        # Never return database URLs, passwords, hostnames or driver diagnostics.
        return JSONResponse(
            status_code=503, content={"status": "unavailable", "database": "unavailable"}
        )
    return JSONResponse(
        content={"status": "ok", "database": "ok"},
        headers={"X-App-Revision": os.environ.get("APP_REVISION", "unknown")},
    )
