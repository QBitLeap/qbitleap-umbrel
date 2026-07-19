import json
import os
import socket
import stat
from html import escape
from datetime import datetime, timezone
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


def get_network_difficulty() -> float | None:
    try:
        return float(rpc("getdifficulty"))
    except (TypeError, ValueError, KeyError, RuntimeError):
        return None


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


def normalize_key(value: object) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


def find_value(records: list[dict], *aliases: str):
    wanted = {normalize_key(alias) for alias in aliases}

    for record in records:
        for key, value in record.items():
            if normalize_key(key) in wanted:
                return value

    return None


def find_max_number(records: list[dict], *aliases: str):
    wanted = {normalize_key(alias) for alias in aliases}
    values: list[float] = []

    for record in records:
        for key, value in record.items():
            if normalize_key(key) not in wanted:
                continue
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue

    return max(values) if values else None


def format_count(value: object) -> str:
    if value is None:
        return "Not reported"

    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        text = str(value).strip()
        return text or "Not reported"


def format_number(value: object) -> str:
    if value is None:
        return "Not reported"

    try:
        number = float(value)
    except (TypeError, ValueError):
        text = str(value).strip()
        return text or "Not reported"

    if number == 0:
        return "0"
    if number >= 1_000_000_000:
        return f"{number / 1_000_000_000:.3g} B"
    if number >= 1_000_000:
        return f"{number / 1_000_000:.3g} M"
    if number >= 1_000:
        return f"{number / 1_000:.3g} K"
    return f"{number:.3f}".rstrip("0").rstrip(".")


def format_difficulty(value: float | None) -> str:
    if value is None:
        return "Not reported"
    return f"{value:,.3f}".rstrip("0").rstrip(".")


def calculate_best_share_percent(
    best_share: float | None,
    network_difficulty: float | None,
) -> float | None:
    if best_share is None or network_difficulty is None or network_difficulty <= 0:
        return None
    return (best_share / network_difficulty) * 100


def format_percent(value: float | None) -> str:
    if value is None:
        return "Not reported"
    if value >= 100:
        return f"{value:,.3f}% — block-level share"
    if value >= 1:
        return f"{value:,.3f}%"
    if value >= 0.001:
        return f"{value:,.6f}%"
    return f"{value:.9f}%"


def format_time(value: object) -> str:
    if value in (None, "", 0, "0"):
        return "Not reported"

    try:
        if isinstance(value, (int, float)) or str(value).strip().replace(".", "", 1).isdigit():
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            moment = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        else:
            moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            moment = moment.astimezone(timezone.utc)
        return moment.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError, OSError, OverflowError):
        return str(value).strip() or "Not reported"


def read_ckpool_stats() -> dict[str, object]:
    stats: dict[str, object] = {
        "users": 0,
        "workers": 0,
        "idle": 0,
        "disconnected": 0,
        "hashrate_1m": "0 H/s",
        "hashrate_5m": "0 H/s",
        "hashrate_1h": "0 H/s",
        "accepted": "Not reported",
        "rejected": "Not reported",
        "best_share": "Not reported",
        "best_share_value": None,
        "last_share": "Not reported",
        "last_block": "Never reported",
        "blocks_found": "Not reported",
        "updated": "Not reported",
    }

    try:
        records = []
        for line in CKPOOL_STATUS_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if isinstance(record, dict):
                records.append(record)

        if not records:
            return stats

        stats["users"] = int(float(find_value(records, "Users", "usercount") or 0))
        stats["workers"] = int(float(find_value(records, "Workers", "workercount") or 0))
        stats["idle"] = int(float(find_value(records, "Idle", "idleworkers") or 0))
        stats["disconnected"] = int(float(find_value(records, "Disconnected", "disconnectedworkers") or 0))

        for output_key, aliases in {
            "hashrate_1m": ("hashrate1m", "hashrate_1m"),
            "hashrate_5m": ("hashrate5m", "hashrate_5m"),
            "hashrate_1h": ("hashrate1hr", "hashrate1h", "hashrate_1h"),
        }.items():
            value = find_value(records, *aliases)
            text = str(value).strip() if value is not None else "0"
            stats[output_key] = f"{text or '0'} H/s"

        stats["accepted"] = format_count(find_value(
            records,
            "Accepted", "acceptedshares", "sharesaccepted", "validshares", "Shares",
        ))
        stats["rejected"] = format_count(find_value(
            records,
            "Rejected", "rejectedshares", "sharesrejected", "invalidshares",
        ))

        best_share = find_max_number(
            records,
            "bestshare", "bestever", "bestdifficulty", "bestsharedifficulty",
        )
        stats["best_share"] = format_number(best_share)
        stats["best_share_value"] = best_share

        stats["blocks_found"] = format_count(find_value(
            records,
            "blocks", "blockcount", "blocksfound", "solvedblocks", "acceptedblocks",
        ))

        stats["last_share"] = format_time(find_value(
            records,
            "lastshare", "lastsharetime", "lastacceptedshare", "lastacceptedsharetime",
        ))
        stats["last_block"] = format_time(find_value(
            records,
            "lastblock", "lastblocktime", "lastblockfound", "lastblockfoundtime",
        ))
        stats["updated"] = format_time(find_value(records, "lastupdate", "updated"))
        return stats
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return stats


def get_ckpool_status() -> tuple[str, str, dict[str, object]]:
    process_running = ckpool_socket_is_running()
    stratum_listening = ckpool_stratum_is_listening()

    if not process_running:
        return "Not Running", "Not Listening", read_ckpool_stats()

    stats = read_ckpool_stats()
    stratum_status = "Listening" if stratum_listening else "Not Listening"
    return "Running", stratum_status, stats


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    qbit_status = get_qbit_status()
    (
        ckpool_status,
        stratum_status,
        ckpool_stats,
    ) = get_ckpool_status()
    miner_address = get_miner_address()
    network_difficulty = get_network_difficulty()
    best_share_value = ckpool_stats.get("best_share_value")
    best_share_percent = calculate_best_share_percent(
        best_share_value if isinstance(best_share_value, (int, float)) else None,
        network_difficulty,
    )
    progress_width = min(max(best_share_percent or 0, 0), 100)

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
            <h2 style="margin-top: 0; color: #bbb;">Solo Mining Dashboard</h2>

            {notice_html}

            <section style="
                margin-top: 32px;
                padding: 24px;
                border: 1px solid #333;
                border-radius: 8px;
                background: #181818;
            ">
                <h3 style="margin-top: 0;">Mining Progress</h3>

                <div style="
                    width: 100%;
                    height: 24px;
                    overflow: hidden;
                    border: 1px solid #555;
                    border-radius: 12px;
                    background: #0d0d0d;
                ">
                    <div style="
                        width: {progress_width:.6f}%;
                        height: 100%;
                        background: #20b957;
                    "></div>
                </div>

                <div style="margin-top: 10px; font-size: 20px; font-weight: bold;">
                    {escape(format_percent(best_share_percent))}
                </div>
                <div style="margin-top: 6px; color: #aaa;">
                    Best share compared with current network difficulty. This is a
                    closest-attempt record, not the probability of the next share.
                </div>

                <div style="margin-top: 20px;">
                    Best share: {escape(str(ckpool_stats["best_share"]))}
                </div>
                <div style="margin-top: 6px;">
                    Current network difficulty: {escape(format_difficulty(network_difficulty))}
                </div>
                <div style="margin-top: 6px;">
                    Blocks found: {escape(str(ckpool_stats["blocks_found"]))}
                </div>
            </section>

            <section style="
                margin-top: 24px;
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
                        Users: {ckpool_stats["users"]}
                    </div>
                    <div style="margin-top: 6px;">
                        Workers: {ckpool_stats["workers"]}
                    </div>
                    <div style="margin-top: 6px;">
                        Active / idle / disconnected:
                        {ckpool_stats["workers"] - ckpool_stats["idle"]} /
                        {ckpool_stats["idle"]} / {ckpool_stats["disconnected"]}
                    </div>
                    <div style="margin-top: 6px;">
                        Hashrate (1m): {escape(str(ckpool_stats["hashrate_1m"]))}
                    </div>
                    <div style="margin-top: 6px;">
                        Hashrate (5m): {escape(str(ckpool_stats["hashrate_5m"]))}
                    </div>
                    <div style="margin-top: 6px;">
                        Hashrate (1h): {escape(str(ckpool_stats["hashrate_1h"]))}
                    </div>
                    <div style="margin-top: 6px;">
                        Accepted shares: {escape(str(ckpool_stats["accepted"]))}
                    </div>
                    <div style="margin-top: 6px;">
                        Rejected shares: {escape(str(ckpool_stats["rejected"]))}
                    </div>
                    <div style="margin-top: 6px;">
                        Best share: {escape(str(ckpool_stats["best_share"]))}
                    </div>
                    <div style="margin-top: 6px;">
                        Last accepted share: {escape(str(ckpool_stats["last_share"]))}
                    </div>
                    <div style="margin-top: 6px;">
                        Last block found: {escape(str(ckpool_stats["last_block"]))}
                    </div>
                    <div style="margin-top: 6px;">
                        Blocks found: {escape(str(ckpool_stats["blocks_found"]))}
                    </div>
                    <div style="margin-top: 6px; color: #999;">
                        CKPool stats updated: {escape(str(ckpool_stats["updated"]))}
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
