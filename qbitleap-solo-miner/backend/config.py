from pathlib import Path
import secrets

DATA_DIR = Path("/data")
RPC_FILE = DATA_DIR / "rpc_credentials"


def get_rpc_credentials():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if RPC_FILE.exists():
        user, password = RPC_FILE.read_text().strip().split(":", 1)
        return user, password

    user = "qbitleap"
    password = secrets.token_urlsafe(32)

    RPC_FILE.write_text(f"{user}:{password}")

    return user, password
