from __future__ import annotations

import json
import os
import socket
from html import escape
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config import (
    get_miner_address,
    save_miner_address,
)
from qbit import rpc

app = FastAPI(title="Qbit Solo")

CKPOOL_STATUS_PATH = Path(
    os.getenv(
        "CKPOOL_STATUS_PATH",
        "/ckpool-logs/pool/pool.status",
    )
)
CKPOOL_STRATUM_HOST = os.getenv("CKPOOL_STRATUM_HOST", "ckpool")
CKPOOL_STRATUM_PORT = int(os.getenv("CKPOOL_STRATUM_PORT", "3333"))
HALL_OF_BLOCKS_PATH = Path(os.getenv("HALL_OF_BLOCKS_PATH", "/config/hall-of-blocks.json"))
PERMISSIONLESS_TELEMETRY_FILE = Path(
    os.getenv("PERMISSIONLESS_TELEMETRY_FILE", "/telemetry/permissionless.json")
)


def get_qbit_status() -> str:
    try:
        blockchain = rpc("getblockchaininfo")
        blocks = blockchain["blocks"]
        progress = blockchain["verificationprogress"] * 100

        return f"Block {blocks:,}, sync {progress:.2f}%"
    except Exception as error:
        return f"Unavailable — {type(error).__name__}"


def get_network_difficulty() -> float | None:
    try:
        return float(rpc("getdifficulty"))
    except (TypeError, ValueError, KeyError, RuntimeError):
        return None


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


def format_hashrate(value: float) -> str:
    units = ("H/s", "kH/s", "MH/s", "GH/s", "TH/s", "PH/s", "EH/s")
    number = max(0.0, float(value))
    unit = units[0]
    for candidate in units:
        unit = candidate
        if number < 1000 or candidate == units[-1]:
            break
        number /= 1000
    return f"{number:.2f} {unit}"


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
    if value is None or value <= 0:
        return "0%"
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



def parse_count(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text or text.lower() == "not reported":
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def load_hall_of_blocks() -> dict[str, object]:
    default = {"observed_blocks_found": 0, "blocks": []}
    try:
        data = json.loads(HALL_OF_BLOCKS_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return default
        blocks = data.get("blocks", [])
        if not isinstance(blocks, list):
            blocks = []
        observed = parse_count(data.get("observed_blocks_found")) or 0
        return {"observed_blocks_found": observed, "blocks": blocks}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return default


def save_hall_of_blocks(data: dict[str, object]) -> None:
    HALL_OF_BLOCKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = HALL_OF_BLOCKS_PATH.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(HALL_OF_BLOCKS_PATH)


def get_tip_block_record(
    miner_address: str,
    best_share: float | None,
    network_difficulty: float | None,
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    record: dict[str, object] = {
        "height": "Not reported",
        "found": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "finder": miner_address or "Not configured",
        "reward": "Not reported",
        "best_share": format_number(best_share),
        "network_difficulty": format_difficulty(network_difficulty),
        "difficulty_ratio": format_percent(
            calculate_best_share_percent(best_share, network_difficulty)
        ),
    }

    try:
        blockchain = rpc("getblockchaininfo")
        height = int(blockchain["blocks"])
        block_hash = rpc("getblockhash", [height])
        block = rpc("getblock", [block_hash, 2])
        record["height"] = height

        block_time = block.get("time") if isinstance(block, dict) else None
        if block_time:
            record["found"] = format_time(block_time)

        transactions = block.get("tx", []) if isinstance(block, dict) else []
        if transactions and isinstance(transactions[0], dict):
            reward = sum(
                float(output.get("value", 0))
                for output in transactions[0].get("vout", [])
                if isinstance(output, dict)
            )
            record["reward"] = f"{reward:.8f} QBIT"
    except (TypeError, ValueError, KeyError, RuntimeError):
        pass

    return record


def update_hall_of_blocks(
    reported_blocks_found: object,
    miner_address: str,
    best_share: float | None,
    network_difficulty: float | None,
    reported_history: list[dict] | None = None,
) -> dict[str, object]:
    hall = load_hall_of_blocks()
    current_count = parse_count(reported_blocks_found)
    observed_count = parse_count(hall.get("observed_blocks_found")) or 0
    blocks = hall.get("blocks", [])
    if not isinstance(blocks, list):
        blocks = []

    known_heights = {str(block.get("height")) for block in blocks if block.get("height") is not None}
    for event in reversed(reported_history or []):
        height = event.get("height")
        if height is None or str(height) in known_heights:
            continue
        record = {
            "height": height,
            "found": format_time(event.get("found_at")),
            "finder": event.get("worker") or miner_address or "Not reported",
            "reward": "Paid directly to configured Qbit address",
            "best_share": "Block-level share",
            "network_difficulty": format_difficulty(network_difficulty),
            "difficulty_ratio": "100% — accepted block",
        }
        if event.get("block_hash"):
            record["block_hash"] = event["block_hash"]
        blocks.append(record)
        known_heights.add(str(height))

    if reported_history:
        # A block can be observed first by the worker submission path and again
        # by the chain scanner. When detailed history exists, its unique block
        # identities are more reliable than an aggregate event count.
        unique_reported_blocks = {
            str(event.get("height") or event.get("block_hash"))
            for event in reported_history
            if event.get("height") is not None or event.get("block_hash")
        }
        current_count = len(unique_reported_blocks)

    if current_count is not None and current_count > max(observed_count, len(blocks)):
        for _ in range(current_count - max(observed_count, len(blocks))):
            blocks.append(
                get_tip_block_record(miner_address, best_share, network_difficulty)
            )
    if current_count is not None and current_count >= observed_count:
        hall = {"observed_blocks_found": current_count, "blocks": blocks}
        try:
            save_hall_of_blocks(hall)
        except OSError:
            pass
    elif current_count is not None and current_count < observed_count:
        # Preserve permanent history across CKPool restarts or counter resets.
        hall["blocks"] = blocks

    return hall


def render_hall_of_blocks(hall: dict[str, object]) -> str:
    blocks = hall.get("blocks", [])
    if not isinstance(blocks, list):
        blocks = []

    total = max(parse_count(hall.get("observed_blocks_found")) or 0, len(blocks))
    if not blocks:
        return f"""
            <div style="margin-top: 14px;">Total Blocks Found: {total:,}</div>
            <p style="margin: 16px 0 0; color: #bbb; line-height: 1.5;">
                No blocks have been mined yet.<br>
                Your first solo block will be permanently recorded here.
            </p>
        """

    entries = []
    for index, block in enumerate(reversed(blocks), start=1):
        display_number = len(blocks) - index + 1
        block_hash_html = ""
        if block.get("block_hash"):
            block_hash_html = (
                '<div style="margin-top: 6px;">Hash: <code>'
                f'{escape(str(block["block_hash"]))}</code></div>'
            )
        entries.append(f"""
            <article style="margin-top: 18px; padding-top: 18px; border-top: 1px solid #333;">
                <strong>Block #{display_number}</strong>
                <div style="margin-top: 10px;">Height: {escape(str(block.get('height', 'Not reported')))}</div>
                <div style="margin-top: 6px;">Found: {escape(str(block.get('found', 'Not reported')))}</div>
                {block_hash_html}
                <div style="margin-top: 6px;">Finder: <code>{escape(str(block.get('finder', 'Not reported')))}</code></div>
                <div style="margin-top: 6px;">Reward: {escape(str(block.get('reward', 'Not reported')))}</div>
                <div style="margin-top: 6px;">Best share: {escape(str(block.get('best_share', 'Not reported')))}</div>
                <div style="margin-top: 6px;">Network difficulty: {escape(str(block.get('network_difficulty', 'Not reported')))}</div>
                <div style="margin-top: 6px;">Difficulty ratio: {escape(str(block.get('difficulty_ratio', 'Not reported')))}</div>
            </article>
        """)

    return f'<div style="margin-top: 14px;">Total Blocks Found: {total:,}</div>' + "".join(entries)


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
        "block_history": [],
    }

    try:
        telemetry = json.loads(PERMISSIONLESS_TELEMETRY_FILE.read_text(encoding="utf-8"))
        workers = telemetry.get("workers", [])
        if not isinstance(workers, list):
            workers = []
        accepted = int(telemetry.get("accepted_shares", 0))
        rejected = int(telemetry.get("rejected_shares", 0))
        last_share = max((int(worker.get("last_share_at", 0)) for worker in workers), default=0)
        blocks = telemetry.get("block_history", {}).get("qbit", [])
        hashrate = float(telemetry.get("current_hashrate_hs", 0))
        stats.update({
            "users": int(telemetry.get("connected_workers", 0) > 0),
            "workers": int(telemetry.get("connected_workers", 0)),
            "idle": sum(1 for worker in workers if not worker.get("active")),
            "hashrate_1m": format_hashrate(hashrate),
            "hashrate_5m": format_hashrate(hashrate),
            "hashrate_1h": format_hashrate(hashrate),
            "accepted": format_count(accepted),
            "rejected": format_count(rejected),
            "last_share": format_time(last_share),
            "last_block": format_time(blocks[0].get("found_at")) if blocks else "Never reported",
            "blocks_found": format_count(len(blocks)),
            "block_history": blocks,
            "updated": format_time(telemetry.get("updated_at")),
        })
        return stats
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass

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
    stratum_listening = ckpool_stratum_is_listening()

    if not stratum_listening:
        return "Not Running", "Not Listening", read_ckpool_stats()

    stats = read_ckpool_stats()
    return "Running", "Listening", stats


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    qbit_status = get_qbit_status()
    ckpool_status, _stratum_status, ckpool_stats = get_ckpool_status()
    miner_address = get_miner_address()
    network_difficulty = get_network_difficulty()
    best_share_value = ckpool_stats.get("best_share_value")
    numeric_best_share = (
        best_share_value if isinstance(best_share_value, (int, float)) else None
    )
    hall = update_hall_of_blocks(
        ckpool_stats.get("blocks_found"),
        miner_address,
        numeric_best_share,
        network_difficulty,
        ckpool_stats.get("block_history") if isinstance(ckpool_stats.get("block_history"), list) else None,
    )
    hall_html = render_hall_of_blocks(hall)

    status_message = request.query_params.get("message", "")
    error_message = request.query_params.get("error", "")
    notice_html = ""

    if status_message:
        notice_html = f"""
        <div style="margin:0 0 24px;padding:14px 16px;border:1px solid #2ecc71;background:#102a1a;color:#8ff0ae;border-radius:6px;">
            {escape(status_message)}
        </div>
        """
    if error_message:
        notice_html = f"""
        <div style="margin:0 0 24px;padding:14px 16px;border:1px solid #e74c3c;background:#2a1010;color:#ffaaaa;border-radius:6px;">
            {escape(error_message)}
        </div>
        """

    configured_address_html = (
        f"<code>{escape(miner_address)}</code>" if miner_address else "Not configured"
    )
    active_workers = max(
        int(ckpool_stats["workers"]) - int(ckpool_stats["idle"]), 0
    )
    accepted_count = parse_count(ckpool_stats.get("accepted")) or 0
    rejected_count = parse_count(ckpool_stats.get("rejected")) or 0
    share_count = accepted_count + rejected_count
    rejected_percent = (rejected_count * 100 / share_count) if share_count else 0.0
    if ckpool_status != "Running":
        mining_status = "Needs Attention"
        mining_status_class = "bad"
    elif active_workers:
        mining_status = "Mining Normally"
        mining_status_class = "good"
    else:
        mining_status = "Ready — Waiting for Miner"
        mining_status_class = "warn"

    return f"""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Qbit Solo</title>
        <style>
            :root {{ color-scheme:dark; --bg:#0c1017; --panel:#151b25; --line:#283142; --text:#f5f7fa; --muted:#98a2b3; --accent:#7c9cff; --good:#36c275; --warn:#e4ad3d; --bad:#f05d68; }}
            * {{ box-sizing:border-box; }}
            body {{ margin:0; background:var(--bg); color:var(--text); font-family:system-ui,-apple-system,sans-serif; }}
            main {{ width:min(760px,calc(100% - 32px)); margin:40px auto; }}
            .header {{ display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:24px; }}
            h1 {{ margin:0; font-size:28px; }}
            .subtitle {{ margin:6px 0 0; color:var(--muted); font-size:14px; font-weight:500; }}
            details.card {{ margin:0 0 18px; padding:0; border:1px solid var(--line); border-radius:14px; background:var(--panel); overflow:hidden; }}
            details.card > summary {{ position:relative; display:flex; align-items:center; justify-content:center; cursor:pointer; font-size:17px; font-weight:700; padding:22px; list-style:none; }}
            details.card > summary::-webkit-details-marker {{ display:none; }}
            details.card > summary::after {{ content:'▸'; position:absolute; right:22px; color:var(--muted); }}
            details.card[open] > summary::after {{ transform:rotate(90deg); }}
            .card-body {{ padding:0 22px 22px; text-align:center; }}
            .service-row {{ display:flex; flex-wrap:wrap; justify-content:center; align-items:center; gap:10px; padding:14px 0; text-align:center; }}
            .service-row + .service-row, .metric-row + .metric-row {{ border-top:1px solid var(--line); }}
            .service-name {{ display:flex; align-items:center; gap:10px; font-weight:650; }}
            .service-dot {{ width:12px; height:12px; border-radius:3px; background:var(--good); flex:0 0 auto; }}
            .service-dot.down {{ background:var(--bad); }}
            .metric-row {{ display:flex; flex-wrap:wrap; justify-content:center; align-items:center; gap:10px; padding:14px 0; text-align:center; }}
            .metric-value {{ font-weight:700; text-align:center; }}
            .good {{ color:var(--good); }} .warn {{ color:var(--warn); }} .bad {{ color:var(--bad); }}
            .muted {{ color:var(--muted); font-size:13px; line-height:1.5; }}
            label {{ display:block; font-weight:600; margin:0 0 8px !important; }}
            input {{ box-sizing:border-box; width:100% !important; border:1px solid var(--line) !important; border-radius:9px !important; padding:12px !important; background:#0e141e !important; color:var(--text) !important; font:inherit; }}
            button {{ border:0 !important; border-radius:9px !important; padding:10px 16px !important; background:var(--accent) !important; color:#08101f !important; font:inherit !important; font-weight:700 !important; cursor:pointer; }}
            article {{ border-color:var(--line) !important; }}
            code {{ overflow-wrap:anywhere; }}
            .footer {{ color:var(--muted); font-size:12px; text-align:center; margin:24px 0 0; }}
        </style>
    </head>
    <body>
        <main>
            <div class="header">
                <div>
                    <h1>Qbit Solo Miner</h1>
                    <div class="subtitle">Permissionless Qbit solo mining</div>
                </div>
                <button type="button" onclick="window.location.href = window.location.pathname + '?refresh=' + Date.now()">Refresh</button>
            </div>
            {notice_html}

            <details class="card" data-section-key="system-status" open>
                <summary>System Status</summary>
                <div class="card-body">
                    <div class="service-row"><span class="service-name"><span class="service-dot{' down' if qbit_status.startswith('Unavailable') else ''}"></span>Qbit Core</span><span class="metric-value">{escape(qbit_status)}</span></div>
                    <div class="service-row"><span class="service-name"><span class="service-dot{' down' if ckpool_status != 'Running' else ''}"></span>Solo Mining</span><span class="metric-value">{escape(ckpool_status)}</span></div>
                    <div class="metric-row"><span>Status</span><span class="metric-value {mining_status_class}">{mining_status}</span></div>
                    <div class="metric-row"><span>Connected Miners</span><span class="metric-value">{active_workers}</span></div>
                    <div class="metric-row"><span>Total Hashrate</span><span class="metric-value">{escape(str(ckpool_stats['hashrate_1m']))}</span></div>
                    <div class="metric-row"><span>Accepted Shares</span><span class="metric-value">{escape(str(ckpool_stats['accepted']))}</span></div>
                    <div class="metric-row"><span>Rejected Shares</span><span class="metric-value">{rejected_percent:.1f}%</span></div>
                    <div class="metric-row"><span>Last Share Received</span><span class="metric-value">{escape(str(ckpool_stats['last_share']))}</span></div>
                    <div class="metric-row"><span>Blocks Found</span><span class="metric-value">{escape(str(ckpool_stats['blocks_found']))}</span></div>
                    <p class="footer">Telemetry updated: {escape(str(ckpool_stats['updated']))}</p>
                </div>
            </details>

            <details class="card" data-section-key="hall-of-blocks-collapsed">
                <summary>🏆 Qbit Solo Blocks Found</summary>
                <div class="card-body">
                {hall_html}
                </div>
            </details>

            <details class="card" data-section-key="payout-address-collapsed">
                <summary>Mining Payout Address</summary>
                <div class="card-body">
                <p style="color:#bbb;line-height:1.5;">Enter the external Qbit mainnet address that should receive any solo-mined block rewards. The app does not hold or manage wallet keys.</p>
                <p>Current address: <strong>{configured_address_html}</strong></p>
                <form method="post" action="/settings/miner-address">
                    <label for="miner_address" style="display:block;margin-bottom:8px;">Qbit mainnet address</label>
                    <input id="miner_address" name="miner_address" type="text" value="{escape(miner_address, quote=True)}" placeholder="qb1..." autocomplete="off" spellcheck="false" required style="box-sizing:border-box;width:100%;padding:12px;border:1px solid #555;border-radius:4px;background:#0d0d0d;color:white;font-family:monospace;font-size:15px;">
                    <button type="submit" style="margin-top:16px;padding:11px 18px;border:0;border-radius:4px;background:#20b957;color:white;font-size:15px;font-weight:bold;cursor:pointer;">Save payout address</button>
                </form>
                </div>
            </details>
            <p class="footer">Automatic refresh every 5 minutes</p>
        </main>
        <script>
            document.querySelectorAll('details[data-section-key]').forEach((section) => {{
                const key = 'qbitleap-section-' + section.dataset.sectionKey;
                const saved = localStorage.getItem(key);
                if (saved !== null) section.open = saved === 'open';
                section.addEventListener('toggle', () => {{
                    localStorage.setItem(key, section.open ? 'open' : 'closed');
                }});
            }});

            // Minimize dashboard polling: refresh only while this tab is visible.
            // A visible dashboard refreshes every five minutes. Returning to a
            // previously hidden tab triggers one immediate refresh for fresh data.
            const refreshIntervalMs = 5 * 60 * 1000;
            let refreshTimer = null;
            let wasHidden = document.hidden;

            function cancelRefresh() {{
                if (refreshTimer !== null) {{
                    clearTimeout(refreshTimer);
                    refreshTimer = null;
                }}
            }}

            function scheduleRefresh() {{
                cancelRefresh();
                if (!document.hidden) {{
                    refreshTimer = setTimeout(() => window.location.reload(), refreshIntervalMs);
                }}
            }}

            document.addEventListener('visibilitychange', () => {{
                if (document.hidden) {{
                    wasHidden = true;
                    cancelRefresh();
                    return;
                }}

                if (wasHidden) {{
                    window.location.reload();
                    return;
                }}

                scheduleRefresh();
            }});

            scheduleRefresh();
        </script>
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
