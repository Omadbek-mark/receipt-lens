"""Application identity and paths; importing settings never reads credentials."""

import os
from pathlib import Path

APP_NAME = "ReceiptLens"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def database_path() -> Path:
    """Keep the existing environment name and default database location compatible."""
    return Path(os.environ.get("SCANNER_DB_PATH", str(PROJECT_ROOT / "data/expenses.sqlite3")))


def public_mode() -> bool:
    return os.environ.get("RECEIPTLENS_PUBLIC") == "1"


def client_ip_header() -> str:
    """Name the header that the deployment's own reverse proxy overwrites per request."""
    return os.environ.get("RECEIPTLENS_CLIENT_IP_HEADER", "X-ReceiptLens-Client-IP")
