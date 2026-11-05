"""Personal expense storage. Every receipt query requires its authenticated owner."""

import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import date
from hashlib import sha256
from pathlib import Path
from threading import Lock

from scanner.accounts import hash_password, normalize_username, verify_password
from scanner.receipts import CATEGORIES, CURRENCIES, parse_amount

AUTH_LOCK = Lock()


class DuplicateReceipt(ValueError):
    pass


class ExpenseStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS login_attempts (
                    username TEXT PRIMARY KEY, failures INTEGER NOT NULL, blocked_until REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS expenses (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                    merchant TEXT NOT NULL, purchased_on TEXT NOT NULL,
                    amount_minor INTEGER NOT NULL CHECK(amount_minor > 0), currency TEXT NOT NULL,
                    category TEXT NOT NULL, note TEXT NOT NULL, image_hash TEXT NOT NULL,
                    image BLOB NOT NULL, ocr_text TEXT NOT NULL, created_at REAL NOT NULL,
                    UNIQUE(user_id, image_hash)
                );
                CREATE INDEX IF NOT EXISTS owner_date ON expenses(user_id, purchased_on);
            """)
        os.chmod(path, 0o600)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA secure_delete=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def register(self, username: str, password: str) -> str:
        username = normalize_username(username)
        with AUTH_LOCK:
            password_hash = hash_password(password)
        user_id = uuid.uuid4().hex
        try:
            with self.connection() as db:
                db.execute("INSERT INTO users VALUES(?,?,?)", (user_id, username, password_hash))
        except sqlite3.IntegrityError as error:
            raise ValueError("Choose a different username.") from error
        return user_id

    def authenticate(self, username: str, password: str) -> tuple[str, str] | None:
        # Bound expensive password work and serialize attempt counters per process.
        with AUTH_LOCK:
            return self._authenticate(username, password)

    def _authenticate(self, username: str, password: str) -> tuple[str, str] | None:
        try:
            username = normalize_username(username)
        except ValueError:
            return None
        now = time.time()
        with self.connection() as db:
            blocked = db.execute(
                "SELECT * FROM login_attempts WHERE username=?", (username,)
            ).fetchone()
            if blocked and blocked["blocked_until"] > now:
                raise ValueError("Too many attempts. Try again in 5 minutes.")
            row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        # Unknown names perform the same expensive KDF, avoiding a fast-path leak.
        stored = row["password_hash"] if row else "scrypt$" + "00" * 16 + "$" + "00" * 32
        valid = verify_password(password, stored)
        with self.connection() as db:
            if row and valid:
                db.execute("DELETE FROM login_attempts WHERE username=?", (username,))
                return row["id"], row["username"]
            failures = (
                blocked["failures"] if blocked and blocked["blocked_until"] > now - 300 else 0
            ) + 1
            db.execute(
                "INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)",
                (username, failures, now + 300 if failures >= 5 else now),
            )
        return None

    def user_exists(self, user_id: str) -> bool:
        with self.connection() as db:
            return db.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone() is not None

    def save(
        self,
        user_id: str,
        *,
        merchant: str,
        purchased_on: str,
        amount: str,
        currency: str,
        category: str,
        note: str,
        source: bytes,
        image: bytes,
        ocr_text: str,
    ) -> str:
        merchant, note = merchant.strip(), note.strip()
        if (
            not 1 <= len(merchant) <= 160
            or len(note) > 1000
            or currency not in CURRENCIES
            or category not in CATEGORIES
        ):
            raise ValueError("Check merchant, category, currency and note length.")
        try:
            if date.fromisoformat(purchased_on).isoformat() != purchased_on:
                raise ValueError
        except ValueError as error:
            raise ValueError("Enter a valid date in YYYY-MM-DD format.") from error
        minor = parse_amount(amount, currency)
        if (
            not source
            or len(source) > 10 * 1024 * 1024
            or not image
            or len(image) > 10 * 1024 * 1024
            or len(ocr_text) > 100_000
        ):
            raise ValueError("Receipt image or text is too large or missing.")
        identifier = uuid.uuid4().hex
        try:
            with self.connection() as db:
                db.execute(
                    "INSERT INTO expenses(id,user_id,merchant,purchased_on,amount_minor,currency,category,note,image_hash,image,ocr_text,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        identifier,
                        user_id,
                        merchant,
                        purchased_on,
                        minor,
                        currency,
                        category,
                        note,
                        sha256(source).hexdigest(),
                        image,
                        ocr_text,
                        time.time(),
                    ),
                )
        except sqlite3.IntegrityError as error:
            if self.has_image(user_id, source):
                raise DuplicateReceipt("This image is already saved in your account.") from error
            raise ValueError("Could not save this expense. Sign in again.") from error
        return identifier

    def has_image(self, user_id: str, source: bytes) -> bool:
        with self.connection() as db:
            return (
                db.execute(
                    "SELECT 1 FROM expenses WHERE user_id=? AND image_hash=?",
                    (user_id, sha256(source).hexdigest()),
                ).fetchone()
                is not None
            )

    def list(self, user_id: str, start: str, end: str, category: str | None = None) -> list[dict]:
        date.fromisoformat(start)
        date.fromisoformat(end)
        if start > end:
            raise ValueError("The start date must be before the end date.")
        sql = "SELECT id,merchant,purchased_on,amount_minor,currency,category,note FROM expenses WHERE user_id=? AND purchased_on BETWEEN ? AND ?"
        params = [user_id, start, end]
        if category:
            sql += " AND category=?"
            params.append(category)
        with self.connection() as db:
            return [
                dict(row)
                for row in db.execute(sql + " ORDER BY purchased_on DESC,created_at DESC", params)
            ]

    def get(self, user_id: str, identifier: str) -> dict | None:
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM expenses WHERE user_id=? AND id=?", (user_id, identifier)
            ).fetchone()
            return dict(row) if row else None

    def similar(
        self, user_id: str, merchant: str, purchased_on: str, minor: int, currency: str
    ) -> bool:
        with self.connection() as db:
            return (
                db.execute(
                    "SELECT 1 FROM expenses WHERE user_id=? AND lower(merchant)=lower(?) AND purchased_on=? AND amount_minor=? AND currency=?",
                    (user_id, merchant.strip(), purchased_on, minor, currency),
                ).fetchone()
                is not None
            )

    def delete(self, user_id: str, identifier: str) -> None:
        with self.connection() as db:
            db.execute("DELETE FROM expenses WHERE user_id=? AND id=?", (user_id, identifier))
