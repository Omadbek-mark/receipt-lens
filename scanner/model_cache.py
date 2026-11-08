"""Session-owned OCR models shared by the two Streamlit workspaces."""

from typing import Any

import streamlit as st

from scanner.ocr import create_engine
from scanner.settings import public_mode


def load_session_engine(language: str) -> Any:
    if public_mode():
        # The pipeline holds the process-wide OCR slot during creation and use.
        return create_engine(language)
    # Mutable predictors must never be shared globally between users.
    pool = st.session_state.setdefault("doc_engines", {})
    if language not in pool:
        pool[language] = create_engine(language)
    return pool[language]
