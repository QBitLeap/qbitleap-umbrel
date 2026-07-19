import ipaddress
import json
import re
from pathlib import Path

CONFIG_DIR = Path("/config")
CREDENTIALS_FILE = CONFIG_DIR / "rpc_credentials"
MINER_ADDRESS_FILE = CONFIG_DIR / "miner_address"
PUBLIC_ENDPOINT_FILE = CONFIG_DIR / "public_mining_endpoint.json"

_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}\.?$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.?$"
)


def get_rpc_credentials() -> tuple[str, str]:
    contents = CREDENTIALS_FILE.read_text(encoding="utf-8").strip()
    user, password = contents.split(":", 1)

    if not user or not password:
        raise ValueError("Invalid RPC credentials file")

    return user, password


def get_miner_address() -> str:
    if not MINER_ADDRESS_FILE.exists():
        return ""

    return MINER_ADDRESS_FILE.read_text(encoding="utf-8").strip()


def save_miner_address(address: str) -> None:
    normalized_address = address.strip()

    if not normalized_address:
        raise ValueError("Qbit payout address cannot be empty")

    if not normalized_address.startswith("qb1"):
        raise ValueError("Mainnet Qbit payout address must begin with qb1")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    MINER_ADDRESS_FILE.write_text(
        f"{normalized_address}\n",
        encoding="utf-8",
    )
    MINER_ADDRESS_FILE.chmod(0o600)


def get_public_mining_endpoint() -> tuple[str, int]:
    if not PUBLIC_ENDPOINT_FILE.exists():
        return "", 3333

    try:
        data = json.loads(PUBLIC_ENDPOINT_FILE.read_text(encoding="utf-8"))
        host = str(data.get("host", "")).strip()
        port = int(data.get("port", 3333))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return "", 3333

    if not 1 <= port <= 65535:
        port = 3333

    return host, port


def _validate_public_host(host: str) -> str:
    normalized = host.strip().rstrip(".")
    if not normalized:
        raise ValueError("Public host or IP cannot be empty")

    lowered = normalized.lower()
    if "://" in normalized or any(character in normalized for character in "/?#@"):
        raise ValueError("Enter only a host name or IP address, without a scheme, path, or port")
    if lowered == "localhost" or lowered.endswith((".local", ".localhost", ".onion")):
        raise ValueError("Enter a publicly reachable Internet host or IP address")

    ip_candidate = normalized
    if normalized.startswith("[") and normalized.endswith("]"):
        ip_candidate = normalized[1:-1]

    try:
        address = ipaddress.ip_address(ip_candidate)
    except ValueError:
        if not _HOSTNAME_RE.fullmatch(normalized):
            raise ValueError("Public host or IP is not valid")
        return normalized.lower()

    if not address.is_global:
        raise ValueError("Enter a public IP address, not a private, loopback, or reserved address")

    return address.compressed


def save_public_mining_endpoint(host: str, port: str | int) -> None:
    normalized_host = _validate_public_host(host)

    try:
        normalized_port = int(str(port).strip())
    except (TypeError, ValueError):
        raise ValueError("Public Stratum port must be a whole number")

    if not 1 <= normalized_port <= 65535:
        raise ValueError("Public Stratum port must be between 1 and 65535")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path = PUBLIC_ENDPOINT_FILE.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(
            {"host": normalized_host, "port": normalized_port},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary_path.chmod(0o600)
    temporary_path.replace(PUBLIC_ENDPOINT_FILE)
