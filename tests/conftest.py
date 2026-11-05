"""Application tests must never create or read a real user's expense database."""

import pytest


@pytest.fixture(autouse=True)
def isolated_expense_database(tmp_path, monkeypatch):
    monkeypatch.setenv("SCANNER_DB_PATH", str(tmp_path / "isolated-expenses.sqlite3"))
