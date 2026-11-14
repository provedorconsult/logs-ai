"""Private RouterOS syslog receiver; only normalized events enter PostgreSQL."""

import asyncio
import ipaddress
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from psycopg.types.json import Jsonb

from logs_ai.db import connect
from logs_ai.main import health as database_health
from logs_ai.migrate import migrate
from logs_ai.mikrotik import extract_frames, normalize


def store(event, source):
    with connect() as conn:
        conn.execute(
            "INSERT INTO log_events(source,severity,message,attributes) VALUES (%s,%s,%s,%s)",
            ("mikrotik:" + source, event["severity"], event["message"], Jsonb(event["attributes"])),
        )


class Receiver:
    def __init__(self, allowed_source, persist=store, queue_size=2048):
        sources = [value.strip() for value in allowed_source.split(",")]
        if not 1 <= len(sources) <= 32 or any(not value for value in sources):
            raise ValueError("Configure one to 32 explicit MikroTik source addresses")
        self.allowed_sources = {ipaddress.ip_address(value) for value in sources}
        if len(self.allowed_sources) != len(sources):
            raise ValueError("Duplicate MikroTik source addresses")
        self.allowed_source = ipaddress.ip_address(sources[0])
        self.instance_id = uuid.uuid4().hex
        self.persist = persist
        self.queue = asyncio.Queue(maxsize=queue_size)
        self.connections = 0
        self.stats = {
            key: 0 for key in ["received", "persisted", "ignored", "rejected", "db_errors"]
        }
        self.database_failed = False
        self.persisted_by_kind = {}
        self.persisted_by_source_kind = {str(source): {} for source in self.allowed_sources}

    async def consume(self):
        while True:
            event = await self.queue.get()
            source = event.get("_source", str(self.allowed_source))
            while True:
                try:
                    await asyncio.to_thread(self.persist, event, source)
                    self.stats["persisted"] += 1
                    kind = event["attributes"]["event_kind"]
                    self.persisted_by_kind[kind] = self.persisted_by_kind.get(kind, 0) + 1
                    by_source = self.persisted_by_source_kind[source]
                    by_source[kind] = by_source.get(kind, 0) + 1
                    self.database_failed = False
                    self.queue.task_done()
                    break
                except Exception:
                    self.database_failed = True
                    self.stats["db_errors"] += 1
                    # Do not log the exception, raw message or connection credentials.
                    await asyncio.sleep(2)

    async def handle(self, reader, writer):
        peer = writer.get_extra_info("peername")
        try:
            permitted = peer and ipaddress.ip_address(peer[0]) in self.allowed_sources
        except ValueError:
            permitted = False
        if not permitted or self.connections >= max(8, len(self.allowed_sources) * 2):
            self.stats["rejected"] += 1
            writer.close()
            await writer.wait_closed()
            return
        self.connections += 1
        buffer = b""
        try:
            while chunk := await reader.read(8192):
                frames, buffer = extract_frames(buffer + chunk)
                for frame in frames:
                    self.stats["received"] += 1
                    event = normalize(frame)
                    if event is None:
                        self.stats["ignored"] += 1
                    else:
                        event["_source"] = str(ipaddress.ip_address(peer[0]))
                        await self.queue.put(event)
            if buffer:
                self.stats["rejected"] += 1  # Never store a truncated frame on disconnect.
        except (ValueError, OSError):
            self.stats["rejected"] += 1
        finally:
            self.connections -= 1
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass


@asynccontextmanager
async def lifespan(app):
    source = os.environ.get("MIKROTIK_ALLOWED_SOURCES") or os.environ.get(
        "MIKROTIK_ALLOWED_SOURCE", ""
    )
    if not source:
        raise RuntimeError("Configure the allowed private MikroTik source")
    try:
        await asyncio.to_thread(migrate)
    except Exception:
        raise RuntimeError("Collector database initialization failed") from None
    receiver = Receiver(source)
    worker = asyncio.create_task(receiver.consume())
    server = await asyncio.start_server(receiver.handle, "0.0.0.0", 5514, backlog=16)
    app.state.receiver = receiver
    try:
        async with server:
            yield
    finally:
        server.close()
        await server.wait_closed()
        try:
            await asyncio.wait_for(receiver.queue.join(), timeout=5)
        except TimeoutError:
            pass
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


app = FastAPI(
    title="logs-ai MikroTik collector",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    receiver = app.state.receiver
    result = await asyncio.to_thread(database_health)
    if receiver.database_failed or receiver.queue.full():
        return JSONResponse(
            status_code=503, content={"status": "unavailable", "database": "unavailable"}
        )
    for key, value in receiver.stats.items():
        result.headers["X-Collector-" + key.replace("_", "-")] = str(value)
    return result


@app.get("/metrics")
async def metrics():
    receiver = app.state.receiver
    return {
        **receiver.stats,
        "queued": receiver.queue.qsize(),
        "connections": receiver.connections,
        "persisted_by_kind": receiver.persisted_by_kind,
        "persisted_by_source_kind": receiver.persisted_by_source_kind,
        "instance_id": receiver.instance_id,
        "revision": os.environ.get("APP_REVISION", "unknown"),
    }


def main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001, access_log=False)


if __name__ == "__main__":
    main()
