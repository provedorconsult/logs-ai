import io
import os
import re
from unittest.mock import MagicMock, Mock

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from logs_ai.client_registry import ClientRegistry
from logs_ai.migrate import migrate
from logs_ai.web import db, security, ssh
from logs_ai.web.app import app
from tests.helpers.database_guard import connect_test_database, validate_test_database

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="Disposable PostgreSQL required"
)
INITIAL = "Synthetic-Initial-Pass-1!"
PERSONAL = "Synthetic-Personal-Pass-2!"
ORIGIN = "http://testserver"


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    url = os.environ["TEST_DATABASE_URL"]
    validate_test_database(url)
    with connect_test_database(url) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("WEB_DATABASE_URL", url)
    monkeypatch.setenv("LOG_DATABASE_URL", url)
    monkeypatch.setenv("WEB_PUBLIC_ORIGIN", ORIGIN)
    monkeypatch.setenv("WEB_COOKIE_SECURE", "false")
    monkeypatch.setenv("WEB_SESSION_SECRET", "c" * 64)
    monkeypatch.setenv("WEB_BOOTSTRAP_USERNAME", "SyntheticAdmin")
    monkeypatch.setenv("WEB_BOOTSTRAP_PASSWORD_HASH", security.password_hash(INITIAL))
    monkeypatch.setenv("WEB_INITIAL_CLIENT_IP", "192.168.50.1")
    monkeypatch.setenv("WEB_RECEIVER_HOST", "192.168.50.25")
    monkeypatch.setenv("WEB_SSH_DENY_HOSTS", "192.168.50.25")
    monkeypatch.delenv("CLIENTS_DATABASE_URL", raising=False)
    migrate()
    yield
    with connect_test_database(url) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")


def login(client, username="SyntheticAdmin", password=INITIAL):
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200, response.text
    return {"Origin": ORIGIN, "X-CSRF-Token": response.json()["csrf"]}


def ready(client):
    headers = login(client)
    response = client.post(
        "/api/auth/password",
        json={"current_password": INITIAL, "new_password": PERSONAL},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return {"Origin": ORIGIN, "X-CSRF-Token": response.json()["csrf"]}


def test_first_login_gate_rotation_csrf_and_old_password():
    with TestClient(app) as client:
        assert client.get("/api/dashboard").status_code == 401
        headers = login(client)
        assert client.get("/api/auth/me").json()["user"]["must_change_password"]
        for path in (
            "/api/dashboard",
            "/api/reports",
            "/api/clients",
            "/api/users",
            "/api/reports/export/csv",
        ):
            assert client.get(path).status_code == 403
        assert (
            client.post(
                "/api/auth/password", json={"current_password": INITIAL, "new_password": PERSONAL}
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/auth/password",
                json={"current_password": INITIAL, "new_password": PERSONAL},
                headers={**headers, "Origin": "https://evil.invalid"},
            ).status_code
            == 403
        )
        old_cookie = client.cookies.get("logsai_local_session")
        response = client.post(
            "/api/auth/password",
            json={"current_password": INITIAL, "new_password": PERSONAL},
            headers=headers,
        )
        assert response.status_code == 200
        assert old_cookie != client.cookies.get("logsai_local_session")
        assert client.get("/api/dashboard").status_code == 200
        assert (
            client.post(
                "/api/auth/login",
                json={"username": "SyntheticAdmin", "password": INITIAL},
                headers={"Origin": ORIGIN},
            ).status_code
            == 401
        )
        assert "httponly" in response.headers["set-cookie"].lower()


def test_reports_filters_pagination_csv_pdf_and_no_metadata_secrets():
    with TestClient(app) as client:
        ready(client)
        with connect_test_database(os.environ["TEST_DATABASE_URL"]) as conn:
            for i in range(30):
                conn.execute(
                    "INSERT INTO log_events(source,severity,message,attributes) "
                    "VALUES (%s,6,%s,%s)",
                    (
                        "mikrotik:192.168.50.1",
                        "=synthetic-formula" if i == 0 else "ppp.user.created",
                        Jsonb(
                            {
                                "event_kind": "ppp.user.created",
                                "username": "synthetic",
                                "normalization_previous": {"secret": "hidden"},
                            }
                        ),
                    ),
                )
        response = client.get("/api/reports?page_size=10&page=2")
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 30 and len(response.json()["items"]) == 10
        assert "normalization_previous" not in response.text
        assert client.get("/api/reports?q=nosuchvalue").json()["total"] == 0
        assert client.get("/api/reports?q=%25").json()["total"] == 0
        csv = client.get("/api/reports/export/csv")
        assert csv.status_code == 200, csv.text
        assert "'=synthetic-formula" in csv.text
        assert csv.headers["x-export-truncated"] == "false"
        pdf = client.get("/api/reports/export/pdf")
        assert pdf.status_code == 200, pdf.text[:100]
        assert pdf.content.startswith(b"%PDF-")
        assert client.get("/api/reports?severity=99").status_code == 422
        assert (
            client.get("/api/reports?from=2020-01-01T00:00:00Z&to=2026-01-01T00:00:00Z").status_code
            == 422
        )
        assert client.get("/api/dashboard").json()["counts"]["total"] == 30
        with db.logs() as conn, pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute("DELETE FROM log_events")


def test_roles_last_admin_and_session_revocation():
    with TestClient(app) as client:
        headers = ready(client)
        body = {"username": "SyntheticAdmin", "role": "viewer", "active": True}
        assert client.put("/api/users/1", json=body, headers=headers).status_code == 409
        assert (
            client.post(
                "/api/users",
                json={"username": "Reader", "role": "viewer", "password": INITIAL},
                headers=headers,
            ).status_code
            == 201
        )
        with TestClient(app) as reader:
            rh = login(reader, "Reader", INITIAL)
            changed = reader.post(
                "/api/auth/password",
                json={"current_password": INITIAL, "new_password": PERSONAL},
                headers=rh,
            )
            assert changed.status_code == 200
            assert reader.get("/api/reports").status_code == 200
            assert reader.get("/api/users").status_code == 403
            assert reader.get("/api/clients").status_code == 403
            users = client.get("/api/users").json()
            ident = next(u["id"] for u in users if u["username"] == "Reader")
            assert (
                client.put(
                    "/api/users/" + str(ident),
                    json={"username": "Reader", "role": "viewer", "active": False},
                    headers=headers,
                ).status_code
                == 200
            )
            assert reader.get("/api/reports").status_code == 401


def test_clients_registry_scripts_validation_and_no_ssh_password_storage(monkeypatch):
    with TestClient(app) as client:
        headers = ready(client)
        body = {
            "name": "Synthetic edge",
            "source_ip": "192.168.50.2",
            "host_fingerprint": "SHA256:" + "a" * 43,
        }
        response = client.post("/api/clients", json=body, headers=headers)
        assert response.status_code == 201, response.text
        ident = response.json()["id"]
        config = client.get(f"/api/clients/{ident}/config/install")
        assert ':local destination "192.168.50.25"' in config.text
        assert ':local source "192.168.50.2"' in config.text
        registry = ClientRegistry(os.environ["TEST_DATABASE_URL"], ttl=0)
        assert len(registry.sources()) == 2
        called = []
        monkeypatch.setattr(ssh, "apply", lambda c, u, p: called.append((c["id"], u)))
        assert (
            client.post(
                f"/api/clients/{ident}/apply",
                json={"username": "operator", "password": "not-persisted", "confirm": True},
                headers=headers,
            ).status_code
            == 200
        )
        assert called == [(ident, "operator")]
        assert "not-persisted" not in client.get("/api/clients").text
        body["enabled"] = False
        assert client.put(f"/api/clients/{ident}", json=body, headers=headers).status_code == 200
        assert len(registry.sources()) == 1
        assert (
            client.post(
                "/api/clients", json={**body, "source_ip": "169.254.169.254"}, headers=headers
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/clients",
                json={**body, "source_ip": "192.168.50.3", "action_name": "bad-name"},
                headers=headers,
            ).status_code
            == 422
        )


def test_ssh_key_mismatch_prevents_authentication(monkeypatch):
    transport = Mock()
    transport.get_remote_server_key.return_value.asbytes.return_value = b"synthetic-key"
    monkeypatch.setattr(ssh, "connect", lambda c: transport)
    with pytest.raises(ValueError, match="Nenhuma credencial"):
        ssh.apply(
            {"source_ip": "192.168.50.1", "ssh_port": 22, "host_fingerprint": "SHA256:" + "a" * 43},
            "operator",
            "do-not-send",
        )
    transport.auth_password.assert_not_called()
    transport.close.assert_called_once()


def test_login_rate_limit_and_secret_validation_errors():
    with TestClient(app) as client:
        for _ in range(10):
            assert (
                client.post(
                    "/api/auth/login",
                    json={"username": "nobody", "password": "wrong"},
                    headers={"Origin": ORIGIN},
                ).status_code
                == 401
            )
        assert (
            client.post(
                "/api/auth/login",
                json={"username": "nobody", "password": "wrong"},
                headers={"Origin": ORIGIN},
            ).status_code
            == 429
        )
        response = client.post(
            "/api/auth/login",
            json={"username": "nobody", "password": ["not-to-echo"]},
            headers={"Origin": ORIGIN},
        )
        assert response.status_code == 422 and "not-to-echo" not in response.text


def test_bootstrap_never_resets_password_or_recreates_deleted_initial_client():
    with TestClient(app) as client:
        headers = ready(client)
        assert client.delete("/api/clients/1", headers=headers).status_code == 200
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/auth/login",
                json={"username": "SyntheticAdmin", "password": INITIAL},
                headers={"Origin": ORIGIN},
            ).status_code
            == 401
        )
        login(client, password=PERSONAL)
        assert client.get("/api/clients").json()["items"] == []


def test_encoded_bootstrap_hash_and_known_host_import(monkeypatch):
    import base64

    monkeypatch.setenv(
        "WEB_BOOTSTRAP_PASSWORD_HASH",
        "b64:" + base64.b64encode(security.password_hash(INITIAL).encode()).decode(),
    )
    with TestClient(app) as client:
        login(client)
    transport = Mock()
    key = transport.get_remote_server_key.return_value
    key.asbytes.return_value = b"synthetic-known-key"
    channel = transport.open_session.return_value
    channel.makefile.return_value = io.BytesIO(
        b"logs-ai: private TCP/CEF forwarding configured; verify persisted events at the receiver\n"
    )
    channel.recv_exit_status.return_value = 0
    channel.exit_status_ready.return_value = True
    sftp = MagicMock()
    monkeypatch.setattr(ssh, "connect", lambda _: transport)
    monkeypatch.setattr(ssh.paramiko.SFTPClient, "from_transport", lambda _: sftp)
    ssh.apply(
        {
            "source_ip": "192.168.50.1",
            "ssh_port": 22,
            "host_fingerprint": ssh.fingerprint(key),
            "action_name": "logsaiPrivate",
        },
        "synthetic-operator",
        "synthetic-ssh-password",
    )
    transport.auth_password.assert_called_once_with(
        "synthetic-operator", "synthetic-ssh-password", fallback=False
    )
    command = channel.exec_command.call_args.args[0]
    assert re.fullmatch(r"/import file-name=logsai-[a-f0-9]{32}\.rsc", command)
    sftp.remove.assert_called_once_with(command.removeprefix("/import file-name="))
