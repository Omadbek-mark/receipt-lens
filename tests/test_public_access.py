from collections import deque
from types import SimpleNamespace

import pytest

from scanner import public_access
from scanner.accounts import hash_password


def test_public_rate_limit_counts_clients_and_enforces_shared_budget(monkeypatch):
    monkeypatch.setenv("RECEIPTLENS_PUBLIC", "1")
    headers = {"X-ReceiptLens-Client-IP": "192.0.2.1"}
    monkeypatch.setattr(
        public_access, "st", SimpleNamespace(context=SimpleNamespace(headers=headers))
    )
    monkeypatch.setattr(public_access, "_events", {"translation": deque()})
    monkeypatch.setattr(public_access, "LIMITS", {"translation": (60, 2, 3)})
    monkeypatch.setattr(public_access, "monotonic", lambda: 100)
    public_access.reserve("translation")
    public_access.reserve("translation")
    with pytest.raises(public_access.RequestLimitExceeded):
        public_access.reserve("translation")
    headers["X-ReceiptLens-Client-IP"] = "192.0.2.2"
    public_access.reserve("translation")
    headers["X-ReceiptLens-Client-IP"] = "192.0.2.3"
    with pytest.raises(public_access.RequestLimitExceeded):
        public_access.reserve("translation")

    monkeypatch.setattr(public_access, "monotonic", lambda: 160)
    public_access.reserve("translation")


def test_public_rate_limit_reads_configured_proxy_header(monkeypatch):
    monkeypatch.setenv("RECEIPTLENS_PUBLIC", "1")
    monkeypatch.setenv("RECEIPTLENS_CLIENT_IP_HEADER", "X-Real-Ip")
    # A client-supplied default header must not create a separate budget.
    headers = {"X-Real-Ip": "192.0.2.1", "X-ReceiptLens-Client-IP": "192.0.2.9"}
    monkeypatch.setattr(
        public_access, "st", SimpleNamespace(context=SimpleNamespace(headers=headers))
    )
    monkeypatch.setattr(public_access, "_events", {"ocr": deque()})
    monkeypatch.setattr(public_access, "LIMITS", {"ocr": (60, 1, 10)})
    monkeypatch.setattr(public_access, "monotonic", lambda: 100)
    public_access.reserve("ocr")
    headers["X-ReceiptLens-Client-IP"] = "192.0.2.10"
    with pytest.raises(public_access.RequestLimitExceeded):
        public_access.reserve("ocr")


def test_public_registration_uses_five_character_minimum(monkeypatch):
    monkeypatch.setenv("RECEIPTLENS_PUBLIC", "1")
    with pytest.raises(ValueError, match="between 5 and 128"):
        hash_password("ab12")
    assert hash_password("abc12").startswith("scrypt$")
