from pathlib import Path

CREDENTIALS_FILE = Path("/config/rpc_credentials")


def get_rpc_credentials() -> tuple[str, str]:
    contents = CREDENTIALS_FILE.read_text(encoding="utf-8").strip()
    user, password = contents.split(":", 1)

    if not user or not password:
        raise ValueError("Invalid RPC credentials file")

    return user, password
