"""A transparent TCP relay used as an observation point in the isolated lab."""

from __future__ import annotations

import asyncio
import os
import socket
from pathlib import Path
from time import monotonic

from .alerting import write_alert


LISTEN_HOST = os.getenv("RELAY_LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.getenv("RELAY_LISTEN_PORT", "20000"))
UPSTREAM_HOST = os.getenv("RELAY_UPSTREAM_HOST", "dnp3-outstation")
UPSTREAM_PORT = int(os.getenv("RELAY_UPSTREAM_PORT", "20000"))
AUTHORIZED_CLIENT_HOST = os.getenv("AUTHORIZED_DNP3_CLIENT_HOST", "dnp3-live-gateway")
ALERT_PATH = Path(os.getenv("ALERT_PATH", "/var/log/ics-ids/alerts.jsonl"))
ALERT_COOLDOWN_SECONDS = max(0.0, float(os.getenv("UNAPPROVED_ALERT_COOLDOWN_SECONDS", "5")))
last_alert_at: dict[str, float] = {}


def authorized_client_ips() -> set[str]:
    try:
        return set(socket.gethostbyname_ex(AUTHORIZED_CLIENT_HOST)[2])
    except socket.gaierror as exc:
        print(f"could not resolve authorized DNP3 client {AUTHORIZED_CLIENT_HOST}: {exc}", flush=True)
        return set()


def emit_unapproved_source(source: str) -> None:
    now = monotonic()
    if now - last_alert_at.get(source, float("-inf")) < ALERT_COOLDOWN_SECONDS:
        return
    last_alert_at[source] = now
    alert = write_alert(
        ALERT_PATH,
        sensor="dnp3-tap",
        rule_id="OT-DNP3-UNAUTHORIZED-SOURCE-001",
        severity="high",
        evidence={"reason": "DNP3 client is not on the lab allowlist", "authorized_client": AUTHORIZED_CLIENT_HOST},
        event={
            "source": source,
            "destination": UPSTREAM_HOST,
            "protocol": "DNP3",
            "scenario": "dnp3-live-lab",
        },
    )
    print(f"unapproved DNP3 client: {alert}", flush=True)


async def copy_stream(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def relay(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
    peer = client_writer.get_extra_info("peername")
    source = str(peer[0]) if peer else "unknown"
    if source not in authorized_client_ips():
        emit_unapproved_source(source)
    try:
        upstream_reader, upstream_writer = await asyncio.open_connection(UPSTREAM_HOST, UPSTREAM_PORT)
        print(f"relaying DNP3 session from {peer} to {UPSTREAM_HOST}:{UPSTREAM_PORT}", flush=True)
        await asyncio.gather(
            copy_stream(client_reader, upstream_writer),
            copy_stream(upstream_reader, client_writer),
        )
    except OSError as exc:
        print(f"relay connection failure for {peer}: {exc}", flush=True)
        client_writer.close()
        await client_writer.wait_closed()


async def main() -> None:
    server = await asyncio.start_server(relay, LISTEN_HOST, LISTEN_PORT)
    print(f"DNP3 lab relay listening on {LISTEN_HOST}:{LISTEN_PORT}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
