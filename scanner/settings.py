"""Application identity and paths; importing settings never reads credentials."""

import os
from pathlib import Path

APP_NAME = "ReceiptLens"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def database_path() -> Path:
    """Keep the existing environment name and default database location compatible."""
    return Path(os.environ.get("SCANNER_DB_PATH", str(PROJECT_ROOT / "data/expenses.sqlite3")))
