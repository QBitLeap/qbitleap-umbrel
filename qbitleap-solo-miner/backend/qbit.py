import os
import requests

RPC_HOST = os.getenv("QBIT_RPC_HOST", "qbitd")
RPC_PORT = os.getenv("QBIT_RPC_PORT", "8352")
RPC_USER = os.getenv("QBIT_RPC_USER", "")
RPC_PASSWORD = os.getenv("QBIT_RPC_PASSWORD", "")


def rpc(method, params=None):
    if params is None:
        params = []

    response = requests.post(
        f"http://{RPC_HOST}:{RPC_PORT}",
        json={
            "jsonrpc": "1.0",
            "id": "qbitleap",
            "method": method,
            "params": params,
        },
        auth=(RPC_USER, RPC_PASSWORD),
        timeout=5,
    )

    response.raise_for_status()

    return response.json()["result"]
