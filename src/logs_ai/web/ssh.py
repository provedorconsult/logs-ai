import base64
import hashlib
import ipaddress
import os
import re
import socket
import time
import uuid
from pathlib import Path

import paramiko

PRIVATE = [ipaddress.ip_network(net) for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]


def private_address(value):
    try:
        address = ipaddress.IPv4Address(value)
        if not any(address in net for net in PRIVATE):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("Informe um IPv4 de rede privada.") from None
    return str(address)


def validate_client(data):
    private_address(data.source_ip)
    if not re.fullmatch(r"[A-Za-z0-9]{1,32}", data.action_name):
        raise ValueError("A ação RouterOS deve conter somente letras e números, até 32 caracteres.")
    if data.host_fingerprint and not re.fullmatch(
        r"SHA256:[A-Za-z0-9+/]{43}", data.host_fingerprint
    ):
        raise ValueError("Fingerprint SHA256 inválido.")


def script(client, operation="install"):
    root = Path(os.environ.get("MIKROTIK_TEMPLATES_DIR", "scripts/mikrotik"))
    text = (root / f"{operation}-logging.rsc").read_text()
    destination = private_address(os.environ["WEB_RECEIVER_HOST"])
    values = {
        "destination": destination,
        "source": private_address(str(client["source_ip"])),
        "port": int(os.environ.get("WEB_SYSLOG_PORT", "5514")),
        "actionName": client["action_name"],
    }
    import json

    for key, value in values.items():
        literal = str(value) if isinstance(value, int) else json.dumps(value)
        text, count = re.subn(rf"(?m)^:local {key} .*$", f":local {key} {literal}", text)
        if count != 1:
            raise RuntimeError("Template indisponível")
    return text


def fingerprint(key):
    return "SHA256:" + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")


def connect(client):
    host = private_address(str(client["source_ip"]))
    denied = {
        value.strip()
        for value in os.environ.get("WEB_SSH_DENY_HOSTS", "").split(",")
        if value.strip()
    }
    if host in denied:
        raise ValueError("Destino reservado à infraestrutura do servidor.")
    sock = socket.create_connection((host, client["ssh_port"]), timeout=5)
    transport = paramiko.Transport(sock)
    transport.auth_timeout = 10
    transport.banner_timeout = 7
    try:
        transport.start_client(timeout=7)
        return transport
    except Exception:
        transport.close()
        raise


def observed_key(client):
    transport = connect(client)
    try:
        return fingerprint(transport.get_remote_server_key())
    finally:
        transport.close()


def apply(client, username, password):
    if not client["host_fingerprint"]:
        raise ValueError("Confirme o fingerprint por um canal independente antes de aplicar.")
    transport = connect(client)
    path = "logsai-" + uuid.uuid4().hex + ".rsc"
    sftp, created = None, False
    try:
        if fingerprint(transport.get_remote_server_key()) != client["host_fingerprint"]:
            raise ValueError("Chave SSH divergente. Nenhuma credencial foi enviada.")
        transport.auth_password(username, password, fallback=False)
        sftp = paramiko.SFTPClient.from_transport(transport)
        sftp.get_channel().settimeout(10)
        with sftp.open(path, "wx") as file:
            created = True
            file.write(script(client).encode())
        channel = transport.open_session(timeout=10)
        channel.settimeout(25)
        try:
            channel.exec_command("/import file-name=" + path)
            output = channel.makefile("rb").read(16385).decode("utf-8", errors="replace")
            if len(output) > 16384:
                raise ValueError("Resposta SSH excedeu o limite. Confira o estado do roteador.")
            deadline = time.monotonic() + 5
            while not channel.exit_status_ready():
                if time.monotonic() >= deadline:
                    raise TimeoutError("SSH command completion timed out")
                time.sleep(0.1)
            status = channel.recv_exit_status()
            marker = (
                "logs-ai: private TCP/CEF forwarding configured; verify per"
                "sisted events at the receiver"
            )
            if status or len(output) > 16384 or marker not in output or "Script Error" in output:
                raise ValueError(
                    "RouterOS recusou a configuração. Confira colisões de ação/"
                    "regras e a versão TCP/CEF."
                )
        finally:
            channel.close()
    finally:
        if sftp:
            if created:
                try:
                    sftp.remove(path)
                except OSError:
                    pass
            sftp.close()
        transport.close()
