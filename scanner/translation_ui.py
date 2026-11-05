"""Translation stays separate from source OCR and confirmed expense values."""

import os
import time
from hashlib import sha256

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from scanner.expense_reports import safe_csv_cell
from scanner.i18n import option_labels, tr
from scanner.ocr import LANGUAGES
from scanner.pipeline import ProcessedDocument
from scanner.translation import TranslationError, configured_model, translate_lines


def configured_key() -> str:
    if os.environ.get("GEMINI_API_KEY", "").strip():
        return os.environ["GEMINI_API_KEY"].strip()
    try:
        value = st.secrets.get("gemini", {}).get("api_key", "")
        return value.strip() if isinstance(value, str) else ""
    except (FileNotFoundError, StreamlitSecretNotFoundError):
        return ""


def queue_translation() -> None:
    if not st.session_state.get("receipt_busy"):
        st.session_state["receipt_busy"] = True
        st.session_state["receipt_translation_pending"] = True


def render_translation(result: ProcessedDocument, document_key: str) -> None:
    state = st.session_state
    with st.expander(tr("Translate receipt text")):
        key = configured_key()
        busy = state.get("receipt_busy", False)
        st.caption(
            tr(
                "Translation uses Google Gemini. Only the text below is sent after you request it; the receipt image is not sent. Source OCR and saved expense values remain separate."
            )
        )
        st.caption(
            tr(
                "Gemini may make mistakes. On the free API tier, submitted content may be used to improve Google products. Use non-private demo text."
            )
        )
        if not key:
            st.info(
                tr(
                    "Translation is not available on this installation yet. Server setup is required."
                )
            )
        source = st.text_area(
            tr("Review text to translate"),
            value=result.ocr.text,
            height=180,
            key="receipt_translation_input_" + sha256(document_key.encode()).hexdigest()[:16],
            disabled=busy,
        )
        target = st.selectbox(
            tr("Translate to"),
            [language for language in LANGUAGES if language != result.ocr.language],
            index=None,
            placeholder=tr("Choose translation language"),
            format_func=option_labels(LANGUAGES),
            key="receipt_translation_target",
            disabled=busy,
        )
        signature = sha256(
            f"gemini|{configured_model()}|{document_key}|{source}|{target}".encode()
        ).hexdigest()
        if state.get("receipt_translation_view_signature") != signature:
            for name in (
                "receipt_translation_result",
                "receipt_translation_signature",
                "receipt_translation_error",
            ):
                state.pop(name, None)
            state["receipt_translation_view_signature"] = signature
        consent = st.checkbox(
            tr("Send this text to Google Gemini."),
            key="receipt_translation_consent_" + signature[:16],
            disabled=busy,
        )
        already_done = state.get("receipt_translation_signature") == signature
        st.button(
            tr("Translate text"),
            on_click=queue_translation,
            disabled=not key
            or not target
            or not source.strip()
            or not consent
            or busy
            or already_done,
        )
        if state.pop("receipt_translation_pending", False):
            state.pop("receipt_translation_result", None)
            state.pop("receipt_translation_error", None)
            try:
                if not key or not target or not consent:
                    raise TranslationError(
                        "Choose a target language and consent before translating."
                    )
                if time.time() - state.get("receipt_translation_last_at", 0) < 2:
                    raise TranslationError(
                        "Please wait a moment before another translation request."
                    )
                state["receipt_translation_last_at"] = time.time()
                with st.spinner(tr("Translating selected text...")):
                    translated = translate_lines(
                        source.splitlines(), result.ocr.language, target, key
                    )
                state["receipt_translation_result"] = list(zip(source.splitlines(), translated))
                state["receipt_translation_signature"] = signature
            except TranslationError as error:
                state["receipt_translation_error"] = str(error)
            finally:
                state["receipt_busy"] = False
            st.rerun()
        if state.get("receipt_translation_error"):
            st.error(tr(state["receipt_translation_error"]))
        if (
            state.get("receipt_translation_signature") == signature
            and "receipt_translation_result" in state
        ):
            st.dataframe(
                [
                    {
                        tr("Original"): safe_csv_cell(original),
                        tr("Translation"): safe_csv_cell(translated),
                    }
                    for original, translated in state["receipt_translation_result"]
                ],
                hide_index=True,
                width="stretch",
            )
            text = "\n".join(translated for _, translated in state["receipt_translation_result"])
            st.download_button(
                tr("Download translation TXT"),
                text.encode("utf-8"),
                "translation.txt",
                "text/plain; charset=utf-8",
                on_click="ignore",
            )
