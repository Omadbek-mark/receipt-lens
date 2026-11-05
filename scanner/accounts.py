"""Password hashing helpers. Account records live in the SQLite store."""

import hmac
import re
import secrets
from hashlib import scrypt


def normalize_username(username: str) -> str:
    username = username.strip().lower()
    if not re.fullmatch(r"[a-z0-9_]{3,32}", username):
        raise ValueError("Username: use 3–32 lowercase letters, digits or underscores.")
    return username


def hash_password(password: str) -> str:
    if not 5 <= len(password) <= 128:
        raise ValueError("Use a password between 5 and 128 characters.")
    salt = secrets.token_bytes(16)
    key = scrypt(
        password.encode(), salt=salt, n=2**17, r=8, p=1, maxmem=256 * 1024 * 1024, dklen=32
    )
    return f"scrypt${salt.hex()}${key.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not 1 <= len(password) <= 128:
        return False
    _, salt, expected = stored.split("$")
    key = scrypt(
        password.encode(),
        salt=bytes.fromhex(salt),
        n=2**17,
        r=8,
        p=1,
        maxmem=256 * 1024 * 1024,
        dklen=32,
    )
    return hmac.compare_digest(key.hex(), expected)
