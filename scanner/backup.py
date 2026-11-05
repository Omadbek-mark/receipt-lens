"""Create a consistent SQLite backup without exposing credentials or receipt text."""

import argparse
import os
import sqlite3
from pathlib import Path

from scanner.settings import database_path


def backup_database(source: Path, output: Path) -> None:
    source = source.resolve(strict=True)
    output = output.resolve()
    if source == output:
        raise ValueError("Backup must have a different destination.")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Refuse to overwrite an existing backup; restrictive permissions from creation.
    fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as reader:
            with sqlite3.connect(output) as writer:
                reader.backup(writer)
                if writer.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Backup integrity check failed.")
    except Exception:
        output.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = database_path()
    backup_database(source, args.output)
    print("Consistent database backup created. Keep it private.")


if __name__ == "__main__":
    main()
