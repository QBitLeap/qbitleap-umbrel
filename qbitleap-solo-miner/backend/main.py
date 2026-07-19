import json
import os
import socket
import stat
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, quote

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config import get_miner_address, save_miner_address
from qbit import rpc

app = FastAPI(title="QBitLeap")

CKPOOL_SOCKET_PATH = Path(
    os.getenv(
        "CKPOOL_SOCKET_PATH",
        "/ckpool-sock/qbitlab/stratifier",
    )
)
CKPOOL_STATUS_PATH = Path(
    os.getenv(
        "CKPOOL_STATUS_PATH",
        "/ckpool-logs/pool/pool.status",
    )
)
CKPOOL_STRATUM_HOST = os.getenv("CKPOOL_STRATUM_HOST", "ckpool")
CKPOOL_STRATUM_PORT = int(os.getenv("CKPOOL_STRATUM_PORT", "3333"))


def get_qbit_status() -> str:
    try:
        blockchain = rpc("getblockchaininfo")
        blocks = blockchain["blocks"]
        progress = blockchain["verificationprogress"] * 100

        return f"Connected — block {blocks:,}, sync {progress:.2f}%"
    except Exception as error:
        return f"Not Connected — {type(error).__name__}"


def ckpool_socket_is_running() -> bool:
    try:
        return stat.S_ISSOCK(CKPOOL_SOCKET_PATH.stat().st_mode)
    except OSError:
        return False


def ckpool_stratum_is_listening() -> bool:
    try:
        with socket.create_connection(
            (CKPOOL_STRATUM_HOST, CKPOOL_STRATUM_PORT),
            timeout=2,
        ):
            return True
    except OSError:
        return False


def read_ckpool_stats() -> tuple[int, str]:
    try:
        lines = CKPOOL_STATUS_PATH.read_text(
            encoding="utf-8"
        ).splitlines()

        if len(lines) < 2:
            return 0, "0 H/s"

        pool = json.loads(lines[0])
        hashrates = json.loads(lines[1])

        workers = int(pool.get("Workers", 0))
        hashrate = str(hashrates.get("hashrate1m", "0")).strip()

        if not hashrate or hashrate in {"0", "0.0", "0.00"}:
            hashrate = "0"

        return workers, f"{hashrate} H/s"
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0, "0 H/s"


def get_ckpool_status() -> tuple[str, str, int, str]:
    process_running = ckpool_socket_is_running()
    stratum_listening = ckpool_stratum_is_listening()

    if not process_running:
        return "Not Running", "Not Listening", 0, "0 H/s"

    workers, hashrate = read_ckpool_stats()
    stratum_status = "Listening" if stratum_listening else "Not Listening"
    return "Running", stratum_status, workers, hashrate


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    qbit_status = get_qbit_status()
    (
        ckpool_status,
        stratum_status,
        ckpool_workers,
        ckpool_hashrate,
    ) = get_ckpool_status()
    miner_address = get_miner_address()

    dashboard_host = request.url.hostname or "umbrel.local"
    stratum_endpoint = f"stratum+tcp://{dashboard_host}:{CKPOOL_STRATUM_PORT}"

    status_message = request.query_params.get("message", "")
    error_message = request.query_params.get("error", "")

    notice_html = ""

    if status_message:
        notice_html = f"""
        <div style="
            margin: 0 0 24px;
            padding: 14px 16px;
            border: 1px solid #2ecc71;
            background: #102a1a;
            color: #8ff0ae;
            border-radius: 6px;
        ">
            {escape(status_message)}
        </div>
        """

    if error_message:
        notice_html = f"""
        <div style="
            margin: 0 0 24px;
            padding: 14px 16px;
            border: 1px solid #e74c3c;
            background: #2a1010;
            color: #ffaaaa;
            border-radius: 6px;
        ">
            {escape(error_message)}
        </div>
        """

    configured_address_html = (
        f"<code>{escape(miner_address)}</code>"
        if miner_address
        else "Not configured"
    )

    return f"""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta http-equiv="refresh" content="15">
        <title>QBitLeap</title>
    </head>

    <body style="
        margin: 0;
        background: #111;
        color: white;
        font-family: Arial, sans-serif;
    ">
        <main style="
            max-width: 760px;
            margin: 0 auto;
            padding: 40px 24px;
        ">
            <h1 style="margin-bottom: 8px;">QBitLeap</h1>
            <h2 style="margin-top: 0; color: #bbb;">Qbit Solo Miner</h2>

            {notice_html}

            <section style="
                margin-top: 32px;
                padding: 24px;
                border: 1px solid #333;
                border-radius: 8px;
                background: #181818;
            ">
                <h3 style="margin-top: 0;">System status</h3>

                <div style="margin-bottom: 24px;">
                    <strong>Qbit Core</strong>
                    <div style="margin-top: 8px;">
                        Status: {escape(qbit_status)}
                    </div>
                </div>

                <div>
                    <strong>CKPool</strong>
                    <div style="margin-top: 8px;">
                        Status: {escape(ckpool_status)}
                    </div>
                    <div style="margin-top: 6px;">
                        Stratum: {escape(stratum_status)}
                    </div>
                    <div style="margin-top: 6px;">
                        Local endpoint:
                        <code>{escape(stratum_endpoint)}</code>
                    </div>
                    <div style="margin-top: 6px;">
                        Workers: {ckpool_workers}
                    </div>
                    <div style="margin-top: 6px;">
                        Hashrate: {escape(ckpool_hashrate)}
                    </div>
                </div>
            </section>

            <section style="
                margin-top: 24px;
                padding: 24px;
                border: 1px solid #333;
                border-radius: 8px;
                background: #181818;
            ">
                <h3 style="margin-top: 0;">Mining payout address</h3>

                <p style="color: #bbb; line-height: 1.5;">
                    Enter the external Qbit mainnet address that should receive
                    any solo-mined block rewards. The app does not hold or
                    manage wallet keys.
                </p>

                <p>
                    Current address:
                    <strong>{configured_address_html}</strong>
                </p>

                <form method="post" action="/settings/miner-address">
                    <label
                        for="miner_address"
                        style="display:block;margin-bottom:8px;"
                    >
                        Qbit mainnet address
                    </label>

                    <input
                        id="miner_address"
                        name="miner_address"
                        type="text"
                        value="{escape(miner_address, quote=True)}"
                        placeholder="qb1..."
                        autocomplete="off"
                        spellcheck="false"
                        required
                        style="
                            box-sizing: border-box;
                            width: 100%;
                            padding: 12px;
                            border: 1px solid #555;
                            border-radius: 4px;
                            background: #0d0d0d;
                            color: white;
                            font-family: monospace;
                            font-size: 15px;
                        "
                    >

                    <button
                        type="submit"
                        style="
                            margin-top: 16px;
                            padding: 11px 18px;
                            border: 0;
                            border-radius: 4px;
                            background: #20b957;
                            color: white;
                            font-size: 15px;
                            font-weight: bold;
                            cursor: pointer;
                        "
                    >
                        Save payout address
                    </button>
                </form>
            </section>
        </main>
    </body>
    </html>
    """


@app.post("/settings/miner-address")
async def update_miner_address(request: Request):
    try:
        body = await request.body()
        form_data = parse_qs(body.decode("utf-8"))
        miner_address = form_data.get("miner_address", [""])[0]

        save_miner_address(miner_address)

        message = quote(
            "Payout address saved. Restart the app to apply it to CKPool."
        )
        return RedirectResponse(
            url=f"/?message={message}",
            status_code=303,
        )
    except Exception as error:
        error_message = quote(str(error))
        return RedirectResponse(
            url=f"/?error={error_message}",
            status_code=303,
        )
