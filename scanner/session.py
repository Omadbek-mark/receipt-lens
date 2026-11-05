"""Small session-state helpers, independent of Streamlit and AI models."""

from hashlib import sha256
from typing import Any, MutableMapping


def document_key(data: bytes, language: str, original: bool, source: str) -> str:
    digest = sha256(data).hexdigest()
    return sha256(f"{digest}|{language}|{original}|{source}".encode()).hexdigest()


def sync_document(state: MutableMapping[str, Any], key: str | None) -> bool:
    if state.get("doc_active_key") == key:
        return False
    for name in (
        "doc_result",
        "doc_preview",
        "doc_edited_text",
        "doc_error",
        "doc_downloads",
        "doc_download_key",
    ):
        state.pop(name, None)
    state["doc_active_key"] = key
    state["doc_pending"] = False
    state["doc_processing"] = False
    return True


def clear_session(state: MutableMapping[str, Any]) -> None:
    epoch = state.get("doc_upload_epoch", 0) + 1
    for name in list(state):
        if name.startswith("doc_"):
            del state[name]
    state["doc_upload_epoch"] = epoch


def export_key(document: str, mode: str, text: str) -> str:
    return sha256(f"{document}|{mode}|{text}".encode()).hexdigest()
