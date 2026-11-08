"""Process-wide request budgets for the single-instance public deployment."""

from collections import deque
from ipaddress import ip_address
from threading import Lock
from time import monotonic

import streamlit as st

from scanner.settings import client_ip_header, public_mode

LIMIT_MESSAGE = "Too many requests. Try again later."

# Action: rolling window (seconds), per client, across the app.
LIMITS = {
    "signup": (86400, 5, 60),
    "login": (300, 20, 120),
    "upload": (300, 20, 120),
    "ocr": (300, 10, 60),
    "translation": (86400, 10, 100),
}
_events: dict[str, deque[tuple[float, str]]] = {action: deque() for action in LIMITS}
_lock = Lock()


class RequestLimitExceeded(ValueError):
    pass


def reserve(action: str) -> None:
    if not public_mode():
        return
    # The configured proxy (Caddy or Traefik) must overwrite this header with the
    # direct peer's address. Direct loopback access uses a shared fallback.
    try:
        client = str(ip_address(st.context.headers.get(client_ip_header(), "")))
    except ValueError:
        client = "unknown"
    window, per_client, total = LIMITS[action]
    with _lock:
        now = monotonic()
        events = _events[action]
        while events and events[0][0] <= now - window:
            events.popleft()
        if len(events) >= total or sum(ip == client for _, ip in events) >= per_client:
            raise RequestLimitExceeded(LIMIT_MESSAGE)
        events.append((now, client))


def accept_upload(file_id: str, state_key: str) -> None:
    """Charge each newly selected file once before the app processes it."""
    if public_mode() and st.session_state.get(state_key) != file_id:
        reserve("upload")
        st.session_state[state_key] = file_id
