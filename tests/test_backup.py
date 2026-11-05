import sqlite3

import pytest

from scanner.backup import backup_database


def test_wal_database_backup_is_consistent_private_and_never_overwrites(tmp_path):
    source, output = tmp_path / "source.sqlite3", tmp_path / "backup.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE sample (value TEXT)")
        connection.execute("INSERT INTO sample VALUES (?)", ("가상 O‘zbek",))
        connection.commit()
        backup_database(source, output)
    with sqlite3.connect(output) as restored:
        assert restored.execute("SELECT value FROM sample").fetchone()[0] == "가상 O‘zbek"
    assert output.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        backup_database(source, output)
    with pytest.raises(ValueError):
        backup_database(source, source)
    with pytest.raises(FileNotFoundError):
        backup_database(tmp_path / "missing.sqlite3", tmp_path / "unused.sqlite3")
    assert not (tmp_path / "unused.sqlite3").exists()
