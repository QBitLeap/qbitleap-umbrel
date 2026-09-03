#!/usr/bin/env python3
import json
import os
import re
import selectors
import socket
import threading
from pathlib import Path


LISTEN_PORT = int(os.environ.get("ROUTER_PORT", "3335"))
BACKEND_HOST = os.environ.get("CKPOOL_BACKEND_HOST", "ckpool")
BACKEND_PORT = int(os.environ.get("CKPOOL_BACKEND_PORT", "3333"))
MINER_ADDRESS_FILE = Path(os.environ.get("MINER_ADDRESS_FILE", "/config/miner_address"))
STATUS_FILE = Path(os.environ.get("ROUTER_STATUS_FILE", "/telemetry/router-status.json"))

active_connections = 0
connection_lock = threading.Lock()


def write_status() -> None:
    payload = json.dumps({"active_connections": active_connections}) + "\n"
    temporary = STATUS_FILE.with_suffix(".tmp")
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, STATUS_FILE)


def qualified_worker(value: object) -> str:
    payout = MINER_ADDRESS_FILE.read_text(encoding="utf-8").strip()
    worker = re.sub(r"[^A-Za-z0-9_-]", "-", str(value))[:32]
    return payout + (f".{worker}" if worker else "")


def rewrite_miner_messages(buffer: bytes, data: bytes) -> tuple[bytes, bytes]:
    buffer += data
    output: list[bytes] = []
    while b"\n" in buffer:
        line, buffer = buffer.split(b"\n", 1)
        try:
            message = json.loads(line)
            if message.get("method") in {"mining.authorize", "mining.submit"} and message.get("params"):
                message["params"][0] = qualified_worker(message["params"][0])
                line = json.dumps(message, separators=(",", ":")).encode()
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        output.append(line + b"\n")
    return buffer, b"".join(output)


def proxy(client: socket.socket) -> None:
    global active_connections
    upstream = None
    selector = selectors.DefaultSelector()
    client_buffer = b""
    try:
        with connection_lock:
            active_connections += 1
            write_status()
        upstream = socket.create_connection((BACKEND_HOST, BACKEND_PORT), timeout=5)
        client.setblocking(False)
        upstream.setblocking(False)
        selector.register(client, selectors.EVENT_READ, upstream)
        selector.register(upstream, selectors.EVENT_READ, client)
        while True:
            for key, _events in selector.select(timeout=1):
                source = key.fileobj
                target = key.data
                data = source.recv(65536)
                if not data:
                    return
                if source is client:
                    client_buffer, data = rewrite_miner_messages(client_buffer, data)
                    if not data:
                        continue
                target.sendall(data)
    except OSError as error:
        print(f"router: connection ended: {error}", flush=True)
    finally:
        selector.close()
        client.close()
        if upstream is not None:
            upstream.close()
        with connection_lock:
            active_connections -= 1
            write_status()


def main() -> None:
    write_status()
    with socket.create_server(("0.0.0.0", LISTEN_PORT), reuse_port=False) as server:
        print(f"Qbit Solo Stratum router listening on {LISTEN_PORT}", flush=True)
        while True:
            client, _address = server.accept()
            threading.Thread(target=proxy, args=(client,), daemon=True).start()


if __name__ == "__main__":
    main()
