import asyncio
import ipaddress
import json

import pytest

from logs_ai.collector import Receiver
from logs_ai.mikrotik import MAX_FRAME, extract_frames, normalize


@pytest.mark.parametrize(
    "message,kind,subject",
    [
        (
            "ppp,info alice logged in, 10.10.0.2 from AA:BB:CC:DD:EE:FF",
            "pppoe.session.started",
            "alice",
        ),
        (
            "ppp,info alice logged out, 60 1000 2000 from AA:BB:CC:DD:EE:FF",
            "pppoe.session.ended",
            "alice",
        ),
        ("ppp,info <pppoe-alice>: authenticated", "pppoe.authenticated", "alice"),
        ("ppp,info <pppoe-alice>: disconnected", "pppoe.session.ended", "alice"),
        (
            "system,info ppp secret alice changed by admin (password=do-not-store)",
            "ppp.user.updated",
            "alice",
        ),
        ("system,info ppp secret alice added by admin", "ppp.user.created", "alice"),
        ("system,info ppp secret alice removed by admin", "ppp.user.deleted", "alice"),
        ("system,info user operator disabled by admin", "routeros.admin_user.disabled", "operator"),
        (
            "system,info,account user admin logged in from 192.0.2.1 via ssh",
            "routeros.admin.login",
            None,
        ),
        (
            "system,info firewall rule changed by admin (token=do-not-store)",
            "routeros.configuration.updated",
            None,
        ),
    ],
)
def test_native_events_are_normalized_without_raw_commands(message, kind, subject):
    event = normalize(("<134>Nov 13 21:00:00 router " + message).encode())
    assert event["attributes"]["event_kind"] == kind
    assert event["attributes"].get("username") == subject
    assert event["attributes"]["router_time"] == "Nov 13 21:00:00"
    assert "do-not-store" not in json.dumps(event)
    assert "password=" not in json.dumps(event)
    assert "token=" not in json.dumps(event)


def test_cef_message_and_topics_are_supported():
    frame = (
        b"<134>1 2026-11-13T21:00:00-03:00 router - - - "
        b"CEF:0|MikroTik|RouterOS|7.24.5|ppp,info|logs-ai: <pppoe-alice>: authenticated|6|"
    )
    event = normalize(frame)
    assert event["attributes"]["event_kind"] == "pppoe.authenticated"
    assert event["attributes"]["username"] == "alice"


def test_cef_extension_does_not_retain_secrets():
    frame = (
        b"CEF:0|MikroTik|RouterOS|7.24.5|system,info|configuration|6|"
        b"msg=ppp secret alice changed by admin (password=do-not-store) cs1=system,info"
    )
    event = normalize(frame)
    assert event["attributes"]["event_kind"] == "ppp.user.updated"
    assert "do-not-store" not in json.dumps(event)


@pytest.mark.parametrize(
    "topics,message,kind",
    [
        (
            "system,info,account",
            "logs-ai-admin: user operator logged in from 192.0.2.1 via ssh",
            "routeros.admin.login",
        ),
        (
            "system,info,account",
            "logs-ai-admin: user operator logged out from 192.0.2.1 via ssh",
            "routeros.admin.logout",
        ),
        ("ppp,info", "logs-ai-ppp: <pppoe-alice>: authenticated", "pppoe.authenticated"),
        ("ppp,info", "logs-ai-ppp: alice logged out, 60 1000 2000", "pppoe.session.ended"),
        (
            "system,info",
            "logs-ai-admin: ppp secret alice changed by operator (password=do-not-store)",
            "ppp.user.updated",
        ),
    ],
)
@pytest.mark.parametrize("routeros_separator", [False, True])
def test_native_hardware_product_cef(topics, message, kind, routeros_separator):
    # Header shape observed on RouterOS 7.24.5; identities/messages are synthetic.
    if routeros_separator:
        message = message.replace(": ", ": : ", 1)
    frame = (
        f"<134>Nov 13 21:00:00 router CEF:0|MikroTik|CCR2116-12G-4S+|"
        f"7.24.5 (stable)|10|{topics}|Low|dvchost=router dvc=192.0.2.10 "
        f"msg={message} app=ssh duser=operator outcome=success src=192.0.2.1"
    ).encode()
    event = normalize(frame)
    assert event["attributes"]["event_kind"] == kind
    assert "do-not-store" not in json.dumps(event)
    assert "dvchost" not in json.dumps(event)
    assert event["attributes"].get("username", "alice") == "alice"
    assert event["attributes"].get("actor", "operator") == "operator"


def test_system_login_cannot_be_misclassified_as_pppoe():
    assert normalize(b"system,info unexpected-prefix user operator logged in") is None


@pytest.mark.parametrize("vendor,product", [("Other", "CCR2116-12G-4S+"), ("MikroTik", "Unknown")])
def test_cef_unrecognized_vendor_or_product_is_ignored(vendor, product):
    assert (
        normalize(f"CEF:0|{vendor}|{product}|7.24.5|10|ppp,info|Low|msg=alice logged in".encode())
        is None
    )


@pytest.mark.parametrize(
    "frame",
    [
        b"",
        b"bad\x00message",
        b"x" * (MAX_FRAME + 1),
        b"unrelated log",
        b"<999>ppp,info alice logged in",
    ],
)
def test_unrelated_or_invalid_messages_are_ignored(frame):
    assert normalize(frame) is None


def test_tcp_octet_counting_and_newline_support_fragmentation():
    a, b = b"ppp,info alice logged in", b"ppp,info alice logged out"
    wire = str(len(a)).encode() + b" " + a + b + b"\n"
    frames, pending = extract_frames(wire[:10])
    assert frames == []
    frames, pending = extract_frames(pending + wire[10:])
    assert frames == [a, b]
    assert pending == b""
    with pytest.raises(ValueError):
        extract_frames(b"99999999 payload")


def test_receiver_uses_private_source_filter_and_persists_normalized_event():
    async def scenario():
        stored = []
        receiver = Receiver(
            "127.0.0.1", persist=lambda event, source: stored.append((event, source))
        )
        worker = asyncio.create_task(receiver.consume())
        server = await asyncio.start_server(receiver.handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        _, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"ppp,info alice logged in, 10.10.0.2 from AA:BB:CC:DD:EE:FF\n")
        await writer.drain()
        for _ in range(100):
            if stored:
                break
            await asyncio.sleep(0.01)
        assert stored[0][1] == "127.0.0.1"
        assert stored[0][0]["attributes"]["address"] == "10.10.0.2"
        assert stored[0][0]["attributes"]["caller_id"] == "AA:BB:CC:DD:EE:FF"
        assert receiver.stats["persisted"] == 1
        writer.close()
        await writer.wait_closed()
        server.close()
        await server.wait_closed()
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)

    asyncio.run(scenario())


def test_receiver_rejects_another_source_without_writing():
    async def scenario():
        receiver = Receiver("192.168.15.1", persist=lambda *a: pytest.fail("No write"))
        server = await asyncio.start_server(receiver.handle, "127.0.0.1", 0)
        reader, writer = await asyncio.open_connection(
            "127.0.0.1", server.sockets[0].getsockname()[1]
        )
        assert await reader.read() == b""
        assert receiver.stats["rejected"] == 1
        writer.close()
        await writer.wait_closed()
        server.close()
        await server.wait_closed()

    asyncio.run(scenario())


def test_database_failure_keeps_event_for_retry_without_logging_raw_data(capsys):
    async def scenario():
        attempts = []

        def persist(event, source):
            attempts.append(event)
            if len(attempts) == 1:
                raise RuntimeError("synthetic-sensitive-driver-detail")

        receiver = Receiver("127.0.0.1", persist=persist)
        await receiver.queue.put(normalize(b"ppp,info alice logged in"))
        worker = asyncio.create_task(receiver.consume())
        await asyncio.wait_for(receiver.queue.join(), timeout=4)
        assert receiver.stats["persisted"] == 1
        assert receiver.stats["db_errors"] == 1
        assert not receiver.database_failed
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)

    asyncio.run(scenario())
    output = capsys.readouterr()
    assert "synthetic-sensitive" not in output.out + output.err


def test_multiple_routers_keep_the_real_peer_during_database_retry():
    async def scenario():
        stored, failed = [], False

        def persist(event, source):
            nonlocal failed
            if source == "127.0.0.2" and not failed:
                failed = True
                raise OSError("synthetic unavailable database")
            stored.append((event["attributes"]["username"], source))

        receiver = Receiver("127.0.0.1,127.0.0.2", persist=persist)
        worker = asyncio.create_task(receiver.consume())
        server = await asyncio.start_server(receiver.handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        for source, name in [("127.0.0.2", "second"), ("127.0.0.1", "first")]:
            _, writer = await asyncio.open_connection("127.0.0.1", port, local_addr=(source, 0))
            writer.write(f"ppp,info {name} logged in\n".encode())
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        for _ in range(100):
            if receiver.stats["received"] == 2:
                break
            await asyncio.sleep(0.01)
        await asyncio.wait_for(receiver.queue.join(), timeout=5)
        assert set(stored) == {("second", "127.0.0.2"), ("first", "127.0.0.1")}
        assert receiver.persisted_by_source_kind == {
            "127.0.0.1": {"pppoe.session.started": 1},
            "127.0.0.2": {"pppoe.session.started": 1},
        }
        server.close()
        await server.wait_closed()
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)

    asyncio.run(scenario())


@pytest.mark.parametrize("sources", ["", "127.0.0.1,", "127.0.0.1,127.0.0.1", "10.0.0.0/8"])
def test_source_allowlist_requires_distinct_exact_addresses(sources):
    with pytest.raises(ValueError):
        Receiver(sources)


def test_managed_sources_are_authoritative_and_revoke_existing_streams():
    class Registry:
        active = {ipaddress.ip_address("127.0.0.1")}

        def sources(self):
            return self.active

    async def scenario():
        registry, stored = Registry(), []
        receiver = Receiver("127.0.0.2", registry=registry, persist=lambda e, s: stored.append(s))
        assert str(receiver.allowed_source) == "127.0.0.1"
        worker = asyncio.create_task(receiver.consume())
        server = await asyncio.start_server(receiver.handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        _, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"ppp,info alice logged in\n")
        await writer.drain()
        for _ in range(100):
            if stored:
                break
            await asyncio.sleep(0.01)
        registry.active = set()
        writer.write(b"ppp,info alice logged out\n")
        await writer.drain()
        await asyncio.sleep(0.05)
        assert stored == ["127.0.0.1"] and receiver.stats["rejected"] == 1
        writer.close()
        await writer.wait_closed()
        server.close()
        await server.wait_closed()
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)

    asyncio.run(scenario())
