"""Local-only browser fixture. Destructive schema setup requires disposable DB guards."""

import os
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


def main():
    url = os.environ["TEST_DATABASE_URL"]
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tests.helpers.database_guard import connect_test_database, validate_test_database

    validate_test_database(url)
    with connect_test_database(url) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
    os.environ.update(
        DATABASE_URL=url,
        WEB_DATABASE_URL=url,
        LOG_DATABASE_URL=url,
        WEB_PUBLIC_ORIGIN="http://127.0.0.1:18030",
        WEB_COOKIE_SECURE="false",
        WEB_SESSION_SECRET="d" * 64,
        WEB_BOOTSTRAP_USERNAME="SyntheticAdmin",
        WEB_INITIAL_CLIENT_IP="192.168.50.1",
        WEB_RECEIVER_HOST="192.168.50.25",
        APP_REVISION="local-ui-preview",
    )
    from logs_ai.web import db, security

    os.environ["WEB_BOOTSTRAP_PASSWORD_HASH"] = security.password_hash("Initial-Test-Pass12!")
    from logs_ai.migrate import migrate

    migrate()
    db.migrate()
    security.bootstrap()
    from psycopg.types.json import Jsonb

    with db.metadata() as conn:
        conn.execute(
            "UPDATE web_clients SET name='Concentrador Matriz' WHERE source_ip='192.168.50.1'"
        )
        for name, ip in [
            ("Borda — Unidade Norte", "192.168.50.2"),
            ("Concentrador Filial", "192.168.50.3"),
        ]:
            conn.execute(
                "INSERT INTO web_clients(name,source_ip) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                (name, ip),
            )
        if not conn.execute("SELECT count(*) AS n FROM log_events").fetchone()["n"]:
            random.seed(8)
            kinds = [
                "pppoe.authenticated",
                "pppoe.session.started",
                "pppoe.session.ended",
                "ppp.user.created",
                "routeros.admin.login",
                "routeros.admin_user.updated",
            ]
            for _ in range(1100):
                event = random.choices(kinds, weights=[28, 24, 26, 3, 8, 2])[0]
                attrs = {
                    "event_kind": event,
                    "username": "cliente.teste" if event.startswith("ppp") else None,
                    "actor": "operador" if event.startswith("routeros") else None,
                }
                ago = timedelta(seconds=random.randrange(1, 24 * 3600))
                conn.execute(
                    "INSERT INTO log_events(source,severity,message,attributes,received_at) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (
                        "mikrotik:192.168.50." + str(random.randrange(1, 4)),
                        random.choices([6, 5, 3], [94, 5, 1])[0],
                        event,
                        Jsonb(attrs),
                        datetime.now(UTC) - ago,
                    ),
                )
    import uvicorn

    from logs_ai.web.app import app

    uvicorn.run(app, host="127.0.0.1", port=18030, access_log=False)


if __name__ == "__main__":
    main()
