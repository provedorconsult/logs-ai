import hashlib
import os
import re
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import psycopg
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from logs_ai.web import db, reports, security, ssh

STATIC = Path(__file__).parent / "static"
DUMMY = security.password_hash(secrets.token_urlsafe(32))
EXPORT_SLOT = threading.BoundedSemaphore(1)
SSH_SLOTS = threading.BoundedSemaphore(2)


@asynccontextmanager
async def lifespan(app):
    from urllib.parse import urlsplit

    origin = urlsplit(os.environ["WEB_PUBLIC_ORIGIN"])
    secret = os.environ.get("WEB_SESSION_SECRET", "")
    if (
        not re.fullmatch("[0-9a-f]{64}", secret)
        or origin.scheme not in ("http", "https")
        or not origin.hostname
        or origin.query
        or origin.fragment
        or origin.path not in ("", "/")
        or origin.username
        or origin.password
    ):
        raise RuntimeError("Configure the web origin and protected session secret")
    if origin.scheme != "https" and origin.hostname not in ("localhost", "127.0.0.1", "testserver"):
        raise RuntimeError("HTTPS is required for the public interface")
    if origin.scheme == "https" and os.environ.get("WEB_COOKIE_SECURE", "true") != "true":
        raise RuntimeError("HTTPS requires secure cookies")
    try:
        db.migrate()
        security.bootstrap()
    except Exception:
        raise RuntimeError("Web database initialization failed") from None
    yield


app = FastAPI(title="logs-ai", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.middleware("http")
async def headers(request, call_next):
    try:
        response = await call_next(request)
    except Exception:
        response = JSONResponse(
            {"detail": "Serviço temporariamente indisponível. Tente novamente."}, status_code=503
        )
    response.headers.update(
        {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "same-origin",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; i"
            "mg-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
            "; form-action 'self'",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }
    )
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    elif request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "no-cache"
    if os.environ.get("WEB_COOKIE_SECURE", "true") == "true":
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


@app.exception_handler(RequestValidationError)
async def invalid(request, exception):
    return JSONResponse({"detail": "Verifique os campos informados."}, status_code=422)


@app.get("/health")
def health():
    try:
        with db.metadata() as conn:
            conn.execute("SELECT 1 FROM web_schema_migrations LIMIT 1").fetchone()
        with db.logs() as conn:
            conn.execute("SELECT 1 FROM log_events LIMIT 1").fetchone()
    except Exception:
        return JSONResponse({"status": "unavailable", "database": "unavailable"}, status_code=503)
    return JSONResponse(
        {"status": "ok", "database": "ok"},
        headers={"X-App-Revision": os.environ.get("APP_REVISION", "unknown")},
    )


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=48)
    password: str = Field(min_length=1, max_length=128)


@app.post("/api/auth/login")
def login(data: Login, request: Request, response: Response):
    security.check_origin(request)
    keys = [
        hashlib.sha256(value.encode()).hexdigest()
        for value in (
            "ip:" + (request.client.host if request.client else "unknown"),
            "user:" + data.username.lower(),
        )
    ]
    with db.metadata() as conn:
        for key in keys:
            limit = conn.execute(
                "INSERT INTO web_login_limits VALUES (%s,1,now()) ON CONFLICT(key) DO UPDATE SET "
                "failures=CASE WHEN web_login_limits.window_start < now()-i"
                "nterval '15 minutes' THEN 1 ELSE web_login_limits.failures"
                "+1 END, "
                "window_start=CASE WHEN web_login_limits.window_start < now"
                "()-interval '15 minutes' THEN now() ELSE web_login_limits."
                "window_start END RETURNING failures",
                (key,),
            ).fetchone()
            if limit["failures"] > 10:
                # Commit the limit before returning; exceptions inside the context roll back.
                conn.commit()
                raise HTTPException(
                    429, "Muitas tentativas. Aguarde 15 minutos.", headers={"Retry-After": "900"}
                )
        user = conn.execute(
            "SELECT * FROM web_users WHERE lower(username)=lower(%s)", (data.username,)
        ).fetchone()
        valid = security.password_matches(data.password, user["password_hash"] if user else DUMMY)
        if not user or not user["active"] or not valid:
            conn.commit()
            raise HTTPException(401, "Usuário ou senha inválidos.")
        for key in keys:
            conn.execute("DELETE FROM web_login_limits WHERE key=%s", (key,))
        conn.execute("UPDATE web_users SET last_login=now() WHERE id=%s", (user["id"],))
        csrf = security.new_session(conn, user["id"], response)
        db.audit(conn, user["id"], "login")
    return {"user": security.public_user(user), "csrf": csrf}


@app.get("/api/auth/me")
def me(request: Request):
    user = security.current_user(request, allow_change=True)
    return {
        "user": security.public_user(user),
        "csrf": security.csrf(request.cookies[security.cookie_name()]),
    }


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    user = security.current_user(request, allow_change=True)
    with db.metadata() as conn:
        conn.execute(
            "DELETE FROM web_sessions WHERE token_hash=%s",
            (security.token_hash(request.cookies[security.cookie_name()]),),
        )
        db.audit(conn, user["id"], "logout")
    response.delete_cookie(
        security.cookie_name(),
        path="/",
        secure=os.environ.get("WEB_COOKIE_SECURE", "true") == "true",
        httponly=True,
        samesite="strict",
    )
    return {"ok": True}


class ChangePassword(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


@app.post("/api/auth/password")
def change_password(data: ChangePassword, request: Request, response: Response):
    user = security.current_user(request, allow_change=True)
    security.validate_password(data.new_password)
    with db.metadata() as conn:
        record = conn.execute(
            "SELECT password_hash FROM web_users WHERE id=%s FOR UPDATE", (user["id"],)
        ).fetchone()
        if not security.password_matches(data.current_password, record["password_hash"]):
            raise HTTPException(400, "Senha atual inválida.")
        if security.password_matches(data.new_password, record["password_hash"]):
            raise HTTPException(422, "Escolha uma senha diferente da atual.")
        conn.execute(
            "UPDATE web_users SET password_hash=%s,must_change_password=false WHERE id=%s",
            (security.password_hash(data.new_password), user["id"]),
        )
        conn.execute("DELETE FROM web_sessions WHERE user_id=%s", (user["id"],))
        csrf = security.new_session(conn, user["id"], response)
        db.audit(conn, user["id"], "password_changed")
    return {"ok": True, "csrf": csrf}


@app.get("/api/dashboard")
def dashboard(request: Request, days: int = 1):
    security.current_user(request)
    if days not in (1, 7, 30):
        raise HTTPException(422, "Período inválido.")
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    with db.logs() as conn:
        counts = conn.execute(
            "SELECT count(*) AS total,count(DISTINCT source) AS sources, "
            "count(*) FILTER(WHERE severity<=3) AS critical, "
            "count(*) FILTER(WHERE attributes->>'event_kind'='pppoe.aut"
            "henticated') AS authentications "
            "FROM log_events WHERE received_at >= %s",
            (start,),
        ).fetchone()
        previous = conn.execute(
            "SELECT count(*) AS n FROM log_events WHERE received_at >= %s AND received_at < %s",
            (start - timedelta(days=days), start),
        ).fetchone()["n"]
        bucket = "hour" if days == 1 else "day"
        trend = conn.execute(
            "SELECT date_trunc(%s,received_at) AS time,count(*) AS coun"
            "t FROM log_events WHERE received_at >= %s GROUP BY 1 ORDER"
            " BY 1",
            (bucket, start),
        ).fetchall()
        sources = conn.execute(
            "SELECT source,count(*) AS count,max(received_at) AS last_s"
            "een FROM log_events WHERE received_at >= %s GROUP BY sourc"
            "e ORDER BY count DESC LIMIT 6",
            (start,),
        ).fetchall()
        kinds = conn.execute(
            "SELECT coalesce(attributes->>'event_kind','other') AS kind"
            ",count(*) AS count FROM log_events WHERE received_at >= %s"
            " GROUP BY 1 ORDER BY count DESC LIMIT 6",
            (start,),
        ).fetchall()
        recent = conn.execute(
            "SELECT "
            + reports.COLUMNS
            + " FROM log_events WHERE received_at >= %s ORDER BY received_at DESC,id DESC LIMIT 7",
            (start,),
        ).fetchall()
    with db.metadata() as conn:
        configured = conn.execute("SELECT count(*) AS n FROM web_clients WHERE enabled").fetchone()[
            "n"
        ]
    return {
        "counts": counts,
        "previous": previous,
        "trend": trend,
        "sources": sources,
        "kinds": kinds,
        "recent": recent,
        "configured_clients": configured,
        "days": days,
        "generated_at": end,
    }


@app.get("/api/reports")
def report(request: Request, page: int = 1, page_size: int = 25):
    security.current_user(request)
    return reports.report(dict(request.query_params), page, page_size)


@app.get("/api/report-options")
def report_options(request: Request):
    security.current_user(request)
    with db.logs() as conn:
        sources = conn.execute(
            "SELECT DISTINCT source FROM log_events ORDER BY source LIMIT 200"
        ).fetchall()
        kinds = conn.execute(
            "SELECT DISTINCT attributes->>'event_kind' AS kind FROM log"
            "_events WHERE attributes ? 'event_kind' ORDER BY kind LIMI"
            "T 80"
        ).fetchall()
    return {"sources": [r["source"] for r in sources], "kinds": [r["kind"] for r in kinds]}


@app.get("/api/reports/export/{format}")
def export(format: str, request: Request):
    security.current_user(request)
    if format not in ("csv", "pdf"):
        raise HTTPException(404)
    if not EXPORT_SLOT.acquire(blocking=False):
        raise HTTPException(429, "Outra exportação está em andamento. Tente novamente.")
    try:
        result = reports.report(
            dict(request.query_params), export_limit=10000 if format == "csv" else 2000
        )
        content = (
            reports.csv_bytes(result["items"])
            if format == "csv"
            else reports.pdf_bytes(result, dict(request.query_params))
        )
        filename = (
            "logs-ai-"
            + datetime.now(UTC).strftime("%Y-%m-%d")
            + ("-parcial" if result["truncated"] else "")
            + "."
            + format
        )
        return Response(
            content,
            media_type="text/csv; charset=utf-8" if format == "csv" else "application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
                "X-Export-Count": str(result["exported"]),
                "X-Result-Total": str(result["total"]),
                "X-Export-Truncated": str(result["truncated"]).lower(),
            },
        )
    finally:
        EXPORT_SLOT.release()


class UserInput(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]{2,47}$")
    role: Literal["admin", "viewer"] = "viewer"
    active: bool = True
    password: str | None = Field(default=None, min_length=12, max_length=128)


@app.get("/api/users")
def users(request: Request):
    security.admin(request)
    with db.metadata() as conn:
        return conn.execute(
            "SELECT id,username,role,active,must_change_password,create"
            "d_at,last_login FROM web_users ORDER BY lower(username)"
        ).fetchall()


@app.post("/api/users", status_code=201)
def create_user(data: UserInput, request: Request):
    actor = security.admin(request)
    if not data.password:
        raise HTTPException(422, "Informe uma senha temporária.")
    security.validate_password(data.password)
    try:
        with db.metadata() as conn:
            user = conn.execute(
                "INSERT INTO web_users(username,password_hash,role,active) "
                "VALUES (%s,%s,%s,%s) RETURNING id",
                (data.username, security.password_hash(data.password), data.role, data.active),
            ).fetchone()
            db.audit(conn, actor["id"], "user_created", user["id"])
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "Esse usuário já existe.") from None
    return {"id": user["id"]}


@app.put("/api/users/{user_id}")
def update_user(user_id: int, data: UserInput, request: Request):
    actor = security.admin(request)
    if data.password:
        security.validate_password(data.password)
    try:
        with db.metadata() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(74329105)")
            old = conn.execute(
                "SELECT * FROM web_users WHERE id=%s FOR UPDATE", (user_id,)
            ).fetchone()
            if not old:
                raise HTTPException(404, "Usuário não encontrado.")
            others = conn.execute(
                "SELECT count(*) AS n FROM web_users WHERE active AND role='admin' AND id<>%s",
                (user_id,),
            ).fetchone()["n"]
            if (
                old["role"] == "admin"
                and old["active"]
                and not (data.active and data.role == "admin")
                and not others
            ):
                raise HTTPException(409, "Mantenha pelo menos um administrador ativo.")
            conn.execute(
                "UPDATE web_users SET username=%s,role=%s,active=%s WHERE id=%s",
                (data.username, data.role, data.active, user_id),
            )
            if data.password:
                conn.execute(
                    "UPDATE web_users SET password_hash=%s,must_change_password=true WHERE id=%s",
                    (security.password_hash(data.password), user_id),
                )
            if data.password or old["role"] != data.role or not data.active:
                conn.execute("DELETE FROM web_sessions WHERE user_id=%s", (user_id,))
            db.audit(conn, actor["id"], "user_updated", user_id)
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "Esse usuário já existe.") from None
    return {"ok": True}


class ClientInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    source_ip: str = Field(max_length=45)
    enabled: bool = True
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_username: str = Field(default="", max_length=64)
    host_fingerprint: str = Field(default="", max_length=60)
    action_name: str = Field(default="logsaiPrivate", max_length=32)
    notes: str = Field(default="", max_length=300)


def get_client(conn, ident):
    row = conn.execute(
        "SELECT id,name,host(source_ip) AS source_ip,enabled,ssh_po"
        "rt,ssh_username,host_fingerprint,action_name,notes,last_ap"
        "ply_status,last_applied_at,created_at FROM web_clients WHE"
        "RE id=%s",
        (ident,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Cliente não encontrado.")
    return row


@app.get("/api/clients")
def clients(request: Request):
    security.admin(request)
    with db.metadata() as conn:
        rows = conn.execute("SELECT id FROM web_clients ORDER BY name").fetchall()
        result = [get_client(conn, row["id"]) for row in rows]
    with db.logs() as conn:
        seen = {
            r["source"]: r["last_seen"]
            for r in conn.execute(
                "SELECT source,max(received_at) AS last_seen FROM log_events GROUP BY source"
            )
        }
    for client in result:
        client["last_seen"] = seen.get("mikrotik:" + client["source_ip"])
    return {
        "items": result,
        "receiver": os.environ["WEB_RECEIVER_HOST"],
        "port": int(os.environ.get("WEB_SYSLOG_PORT", "5514")),
    }


def save_client(data, actor, ident=None):
    updating = ident is not None
    try:
        ssh.validate_client(data)
    except ValueError as exception:
        raise HTTPException(422, str(exception)) from None
    try:
        with db.metadata() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(74329106)")
            count = conn.execute(
                "SELECT count(*) AS n FROM web_clients WHERE enabled AND id<>%s", (ident or 0,)
            ).fetchone()["n"]
            if data.enabled and count >= 32:
                raise HTTPException(409, "Limite de 32 origens ativas por coletor.")
            fields = (
                data.name,
                data.source_ip,
                data.enabled,
                data.ssh_port,
                data.ssh_username,
                data.host_fingerprint,
                data.action_name,
                data.notes,
            )
            if ident:
                locked = conn.execute(
                    "SELECT pg_try_advisory_xact_lock(74329107,%s) AS locked", (ident,)
                ).fetchone()["locked"]
                if not locked:
                    raise HTTPException(409, "Cliente em aplicação SSH; aguarde.")
                get_client(conn, ident)
                conn.execute(
                    "UPDATE web_clients SET name=%s,source_ip=%s,enabled=%s,ssh"
                    "_port=%s,ssh_username=%s,host_fingerprint=%s,action_name=%"
                    "s,notes=%s WHERE id=%s",
                    fields + (ident,),
                )
            else:
                ident = conn.execute(
                    "INSERT INTO web_clients(name,source_ip,enabled,ssh_port,ss"
                    "h_username,host_fingerprint,action_name,notes) VALUES (%s,"
                    "%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                    fields,
                ).fetchone()["id"]
            db.audit(conn, actor["id"], "client_updated" if updating else "client_created", ident)
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "Já existe um cliente com esse endereço IP.") from None
    return {"id": ident}


@app.post("/api/clients", status_code=201)
def create_client(data: ClientInput, request: Request):
    return save_client(data, security.admin(request))


@app.put("/api/clients/{ident}")
def update_client(ident: int, data: ClientInput, request: Request):
    return save_client(data, security.admin(request), ident)


@app.delete("/api/clients/{ident}")
def delete_client(ident: int, request: Request):
    actor = security.admin(request)
    with db.metadata() as conn:
        locked = conn.execute(
            "SELECT pg_try_advisory_xact_lock(74329107,%s) AS locked", (ident,)
        ).fetchone()["locked"]
        if not locked:
            raise HTTPException(409, "Cliente em aplicação SSH; aguarde.")
        get_client(conn, ident)
        conn.execute("DELETE FROM web_clients WHERE id=%s", (ident,))
        db.audit(conn, actor["id"], "client_deleted", ident)
    return {"ok": True}


@app.get("/api/clients/{ident}/config/{operation}")
def config(ident: int, operation: str, request: Request):
    security.admin(request)
    if operation not in ("install", "remove"):
        raise HTTPException(404)
    with db.metadata() as conn:
        client = get_client(conn, ident)
    return Response(
        ssh.script(client, operation),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="logs-ai-{ident}-{operation}.rsc"',
            "Cache-Control": "no-store",
        },
    )


@app.post("/api/clients/{ident}/ssh-key")
def ssh_key(ident: int, request: Request):
    security.admin(request)
    with db.metadata() as conn:
        client = get_client(conn, ident)
    try:
        value = ssh.observed_key(client)
    except Exception:
        raise HTTPException(
            502, "Não foi possível consultar a chave SSH. Confira rota, IP e porta."
        ) from None
    return {
        "fingerprint": value,
        "warning": "Compare por um canal independente antes de salvar. A consu"
        "lta não autentica nem aprova a chave.",
    }


class SshCredentials(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    confirm: bool = False


@app.post("/api/clients/{ident}/apply")
def apply_config(ident: int, data: SshCredentials, request: Request):
    actor = security.admin(request)
    if not data.confirm:
        raise HTTPException(422, "Confirme a aplicação no roteador selecionado.")
    if not SSH_SLOTS.acquire(blocking=False):
        raise HTTPException(429, "Há aplicações SSH em andamento. Aguarde.")
    try:
        with db.metadata() as conn:
            client = get_client(conn, ident)
            locked = conn.execute(
                "SELECT pg_try_advisory_xact_lock(74329107,%s) AS locked", (ident,)
            ).fetchone()["locked"]
            if not locked:
                raise HTTPException(409, "Este roteador já tem uma aplicação em andamento.")
            if not client["enabled"]:
                raise HTTPException(409, "Ative o cliente antes de aplicar.")
            if not client["host_fingerprint"]:
                raise HTTPException(422, "Salve o fingerprint confirmado antes de aplicar.")
            success = False
            reason = "Falha ao aplicar. Confira SSH, SFTP e permissões de importação."
            try:
                ssh.apply(client, data.username, data.password)
                success = True
            except ValueError as exception:
                reason = str(exception)
            except Exception:
                pass
            conn.execute(
                "UPDATE web_clients SET last_apply_status=%s,last_applied_at=now() WHERE id=%s",
                ("success" if success else "failed", ident),
            )
            db.audit(
                conn,
                actor["id"],
                "client_apply_success" if success else "client_apply_failed",
                ident,
            )
    finally:
        SSH_SLOTS.release()
    if not success:
        raise HTTPException(502, reason)
    return {"ok": True, "message": "Configuração aplicada. Confira novos eventos no dashboard."}


app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


@app.get("/")
@app.get("/{path:path}")
def shell(path: str = ""):
    if path not in ("", "relatorios", "clientes", "usuarios"):
        raise HTTPException(404)
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})


def main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080, access_log=False, proxy_headers=False)
