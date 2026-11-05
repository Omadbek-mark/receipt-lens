"""Session-owned OCR models shared by the two Streamlit workspaces."""

from typing import Any

import streamlit as st

from scanner.ocr import create_engine


def load_session_engine(language: str) -> Any:
    # Mutable predictors must never be shared globally between users.
    pool = st.session_state.setdefault("doc_engines", {})
    if language not in pool:
        pool[language] = create_engine(language)
    return pool[language]
