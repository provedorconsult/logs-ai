"""Normalize supported RouterOS events without retaining raw commands or credentials."""

import ipaddress
import re

MAX_FRAME = 16384


def safe_name(value):
    value = value.strip().strip('"<>')
    if (
        not value
        or len(value) > 128
        or any(ord(c) < 32 for c in value)
        or re.search(r"\b(password|pass|secret|token|key)\s*=", value, re.I)
    ):
        return None
    return value


def cef_message(value):
    fields, current, escaped = [], [], False
    for index, char in enumerate(value):
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            fields.append("".join(current))
            current = []
            if len(fields) == 7:
                extension = value[index + 1 :]
                break
        else:
            current.append(char)
    else:
        return None
    if fields[1].lower() != "mikrotik" or fields[2].lower() != "routeros":
        return None
    values = {}
    matches = list(re.finditer(r"(?:^|\s)([A-Za-z][A-Za-z0-9]*)=", extension))
    for number, match in enumerate(matches):
        end = matches[number + 1].start() if number + 1 < len(matches) else len(extension)
        values[match[1]] = extension[match.end() : end].strip()
    message = values.get("msg", fields[5])
    message = message.replace(r"\=", "=").replace(r"\|", "|").replace(r"\n", " ")
    return message, [fields[4], fields[5], values.get("cs1", "")]


def normalize(frame):
    if not frame or len(frame) > MAX_FRAME or b"\x00" in frame:
        return None
    text = frame.decode("utf-8", errors="replace").strip()
    severity = 6
    priority = re.match(r"^<(\d{1,3})>", text)
    if priority:
        if int(priority[1]) > 191:
            return None
        severity = int(priority[1]) % 8
        text = text[priority.end() :]
    timestamp = re.match(
        r"^(?:\d+\s+)?(\d{4}-\d\d-\d\dT[0-9:.+Z-]+|[A-Z][a-z]{2}\s+\d{1,2}\s+\d\d:\d\d:\d\d)\s+",
        text,
    )
    if "CEF:" in text:
        cef = cef_message(text[text.index("CEF:") :])
        if cef is None:
            return None
        body, topic_candidates = cef
    else:
        legacy = re.match(r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d\d:\d\d:\d\d\s+\S+\s+(.*)$", text)
        body = legacy[1] if legacy else text
        topic_candidates = [body]
    topics = set()
    for candidate in topic_candidates:
        if candidate.lower() in {"ppp", "pppoe", "system", "account"}:
            topics.add(candidate.lower())
        prefix = re.match(r"^([a-z]+(?:,[a-z]+)+)(?:\s|$)", candidate.lower())
        if prefix:
            topics.update(set(prefix[1].split(",")) & {"ppp", "pppoe", "system", "account"})
    for _ in range(2):
        body = re.sub(r"^[a-z]+(?:,[a-z]+)+\s+", "", body)
        if body.startswith("logs-ai-ppp:"):
            topics.add("ppp")
        elif body.startswith("logs-ai-admin:"):
            topics.add("system")
        body = re.sub(r"^logs-ai(?:-ppp|-admin)?:\s*", "", body).strip()
    attrs = {"topics": sorted(topics)}
    if timestamp:
        attrs["router_time"] = timestamp[1]
    config = re.match(
        r'^(.*?)\s+(added|changed|removed|deleted|enabled|disabled)\s+by\s+("[^"\r\n]+"|[^\s(]+)',
        body,
        re.I,
    )
    if config and not ({"ppp", "pppoe"} & topics):
        subject, verb, actor = config.groups()
        action = {"added": "created", "changed": "updated", "removed": "deleted"}.get(
            verb.lower(), verb.lower()
        )
        if re.match(r"^/?ppp secret(?:\s|$)", subject, re.I):
            kind = "ppp.user." + action
            attrs["username"] = safe_name(re.sub(r"^/?ppp secret\s*", "", subject, flags=re.I))
        elif re.match(r"^/?user(?:\s|$)", subject, re.I):
            kind = "routeros.admin_user." + action
            attrs["username"] = safe_name(re.sub(r"^/?user\s*", "", subject, flags=re.I))
        else:
            kind = "routeros.configuration." + action
        attrs["actor"] = safe_name(actor)
    else:
        admin = re.match(r'^user\s+("[^"\r\n]+"|\S+)\s+logged\s+(in|out)\b', body, re.I)
        login = re.match(r"^(.*?)\s+logged\s+(in|out)\b", body, re.I)
        link = re.match(r"^<?(?:pppoe-)?([^>:]+)>?:\s*(authenticated|disconnected)\b", body, re.I)
        if admin and "ppp" not in topics:
            kind = "routeros.admin." + ("login" if admin[2].lower() == "in" else "logout")
            attrs["actor"] = safe_name(admin[1])
        elif login:
            kind = "pppoe.session." + ("started" if login[2].lower() == "in" else "ended")
            attrs["username"] = safe_name(login[1].rstrip(":"))
        elif link:
            kind = (
                "pppoe.authenticated"
                if link[2].lower() == "authenticated"
                else "pppoe.session.ended"
            )
            attrs["username"] = safe_name(link[1])
        else:
            return None
        address = re.search(r"logged in,\s*(\d{1,3}(?:\.\d{1,3}){3})\b", body, re.I)
        caller = re.search(r"\bfrom\s+([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\b", body)
        if address and kind.startswith("pppoe."):
            try:
                attrs["address"] = str(ipaddress.ip_address(address[1]))
            except ValueError:
                pass
        if caller and kind.startswith("pppoe."):
            attrs["caller_id"] = caller[1].upper()
    attrs = {key: value for key, value in attrs.items() if value is not None}
    attrs["event_kind"] = kind
    return {"severity": severity, "message": kind, "attributes": attrs}


def extract_frames(buffer):
    """RFC6587 octet counting or newline framing, bounded before retaining payloads."""
    frames = []
    while buffer:
        counted = re.match(rb"^(\d{1,8}) ", buffer)
        if counted:
            length = int(counted[1])
            if length < 1 or length > MAX_FRAME:
                raise ValueError("Invalid syslog frame length")
            end = counted.end() + length
            if len(buffer) < end:
                break
            frames.append(buffer[counted.end() : end])
            buffer = buffer[end:]
        else:
            newline = buffer.find(b"\n")
            if newline < 0:
                if len(buffer) > MAX_FRAME:
                    raise ValueError("Syslog frame is too large")
                break
            if newline > MAX_FRAME:
                raise ValueError("Syslog frame is too large")
            frames.append(buffer[:newline].rstrip(b"\r"))
            buffer = buffer[newline + 1 :]
    return frames, buffer
