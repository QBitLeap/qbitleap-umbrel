import os

import requests

from config import get_rpc_credentials

RPC_HOST = os.getenv("QBIT_RPC_HOST", "qbitd")
RPC_PORT = os.getenv("QBIT_RPC_PORT", "8352")


def rpc(method: str, params: list | None = None):
    user, password = get_rpc_credentials()

    response = requests.post(
        f"http://{RPC_HOST}:{RPC_PORT}",
        json={
            "jsonrpc": "1.0",
            "id": "qbitleap",
            "method": method,
            "params": params or [],
        },
        auth=(user, password),
        timeout=5,
    )

    response.raise_for_status()

    payload = response.json()

    if payload.get("error"):
        raise RuntimeError(payload["error"])

    return payload["result"]
