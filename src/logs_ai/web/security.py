import base64
import hashlib
import hmac
import os
import re
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request

from logs_ai.web.db import metadata

COOKIE = "__Host-logsai_session"
ITERATIONS = 600000


def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def password_matches(password, encoded):
    try:
        algorithm, count, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or not 600000 <= int(count) <= 1000000:
            return False
        computed = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(count)
        ).hex()
        return hmac.compare_digest(computed, expected)
    except (ValueError, TypeError):
        return False


def validate_password(password):
    classes = sum(bool(re.search(p, password)) for p in ("[a-z]", "[A-Z]", "[0-9]", "[^a-zA-Z0-9]"))
    if not 12 <= len(password) <= 128 or classes < 3:
        raise HTTPException(
            422,
            "Use 12 a 128 caracteres e três tipos: maiúsculas, minúsculas, números ou símbolos.",
        )


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def csrf(token):
    return hmac.new(
        bytes.fromhex(os.environ["WEB_SESSION_SECRET"]), token.encode(), "sha256"
    ).hexdigest()


def check_origin(request):
    if request.headers.get("origin") != os.environ["WEB_PUBLIC_ORIGIN"].rstrip("/"):
        raise HTTPException(403, "Origem da requisição não permitida.")


def cookie_name():
    return (
        COOKIE if os.environ.get("WEB_COOKIE_SECURE", "true") == "true" else "logsai_local_session"
    )


def new_session(conn, user_id, response):
    token = secrets.token_urlsafe(32)
    conn.execute("DELETE FROM web_sessions WHERE expires_at < now()")
    conn.execute(
        "INSERT INTO web_sessions(token_hash,user_id,expires_at) VALUES (%s,%s,%s)",
        (token_hash(token), user_id, datetime.now(UTC) + timedelta(hours=8)),
    )
    response.set_cookie(
        cookie_name(),
        token,
        max_age=28800,
        httponly=True,
        secure=os.environ.get("WEB_COOKIE_SECURE", "true") == "true",
        samesite="strict",
        path="/",
    )
    return csrf(token)


def current_user(request: Request, allow_change=False):
    token = request.cookies.get(cookie_name(), "")
    if len(token) > 100:
        raise HTTPException(401, "Sessão inválida.")
    with metadata() as conn:
        user = conn.execute(
            "SELECT u.* FROM web_sessions s JOIN web_users u ON u.id=s.user_id "
            "WHERE s.token_hash=%s AND s.expires_at>now() AND u.active",
            (token_hash(token),),
        ).fetchone()
    if not user:
        raise HTTPException(401, "Entre para continuar.")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        check_origin(request)
        if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), csrf(token)):
            raise HTTPException(403, "Recarregue a página e tente novamente.")
    if user["must_change_password"] and not allow_change:
        raise HTTPException(
            403,
            {
                "code": "password_change_required",
                "message": "Altere a senha inicial para continuar.",
            },
        )
    return user


def admin(request):
    user = current_user(request)
    if user["role"] != "admin":
        raise HTTPException(403, "Acesso restrito a administradores.")
    return user


def public_user(user):
    return {
        k: user[k]
        for k in ("id", "username", "role", "active", "must_change_password", "last_login")
    }


def bootstrap():
    with metadata() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(74329104)")
        created = conn.execute("SELECT count(*) AS n FROM web_users").fetchone()["n"] == 0
        if created:
            username = os.environ.get("WEB_BOOTSTRAP_USERNAME", "")
            encoded = os.environ.get("WEB_BOOTSTRAP_PASSWORD_HASH", "")
            if encoded.startswith("b64:"):
                encoded = base64.b64decode(encoded[4:], validate=True).decode()
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{2,47}", username) or not re.fullmatch(
                r"pbkdf2_sha256\$600000\$[0-9a-f]{32}\$[0-9a-f]{64}", encoded
            ):
                raise RuntimeError("Configure the protected initial administrator hash")
            conn.execute(
                "INSERT INTO web_users(username,password_hash,role) VALUES (%s,%s,%s)",
                (username, encoded, "admin"),
            )
        seed = os.environ.get("WEB_INITIAL_CLIENT_IP", "")
        if seed and created:
            from logs_ai.web.ssh import private_address

            private_address(seed)
            conn.execute(
                "INSERT INTO web_clients(name,source_ip,ssh_port,host_finge"
                "rprint) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT(source_ip) DO NOTHING",
                (
                    "MikroTik principal",
                    seed,
                    int(os.environ.get("WEB_INITIAL_CLIENT_SSH_PORT", "22")),
                    os.environ.get("WEB_INITIAL_CLIENT_FINGERPRINT", ""),
                ),
            )
