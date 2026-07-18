from pathlib import Path

CONFIG_DIR = Path("/config")
CREDENTIALS_FILE = CONFIG_DIR / "rpc_credentials"
MINER_ADDRESS_FILE = CONFIG_DIR / "miner_address"


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
