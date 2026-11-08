"""Streamlit presentation and session model cache; domain logic lives elsewhere."""

import streamlit as st

from scanner.expense_ui import render_expenses
from scanner.exports import image_bytes, text_bytes
from scanner.i18n import UI_LANGUAGES, option_labels, preserve_options, tr
from scanner.imaging import load_image
from scanner.model_cache import load_session_engine
from scanner.ocr import LANGUAGES
from scanner.pipeline import ProcessingError, process_document
from scanner.public_access import RequestLimitExceeded, accept_upload, reserve
from scanner.session import clear_session, document_key, export_key, sync_document
from scanner.settings import APP_NAME, PROJECT_ROOT


def queue_processing() -> None:
    if not st.session_state.get("doc_processing", False):
        st.session_state["doc_pending"] = True
        st.session_state["doc_processing"] = True


def render() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="📄", layout="wide")
    with st.sidebar:
        st.selectbox(
            "Language / Til / 언어",
            UI_LANGUAGES,
            format_func=UI_LANGUAGES.__getitem__,
            key="ui_language",
            on_change=preserve_options,
            disabled=st.session_state.get("receipt_busy", False)
            or st.session_state.get("doc_processing", False),
        )
        workspace = st.radio(
            tr("Workspace"),
            ["Receipt expenses", "Document scanner"],
            format_func=option_labels(),
            key="workspace",
            disabled=st.session_state.get("receipt_busy", False)
            or st.session_state.get("doc_processing", False),
        )
    if workspace == "Receipt expenses":
        render_expenses()
        return
    render_scanner()


def render_scanner() -> None:
    state = st.session_state
    busy = state.get("doc_processing", False)
    st.title(f"{APP_NAME} · {tr('Document scanner')}")
    st.caption(tr("Straighten a page. Read its text. Keep it local."))
    with st.sidebar:
        st.header(tr("Your document"))
        source = st.radio(
            tr("Document source"),
            ["Upload an image", "Try a sample"],
            format_func=option_labels(),
            key="doc_source",
            disabled=busy,
        )
        if not state.get("doc_explicit_language_v2"):
            state["doc_language"] = None
            state["doc_explicit_language_v2"] = True
        language = st.selectbox(
            tr("Document language"),
            list(LANGUAGES),
            index=None,
            placeholder=tr("Choose document language"),
            format_func=option_labels(LANGUAGES),
            key="doc_language",
            disabled=busy,
        )
        uploaded = None
        if source == "Upload an image":
            epoch = state.get("doc_upload_epoch", 0)
            st.caption(tr("JPEG, PNG or HEIC"))
            uploaded = st.file_uploader(
                "JPEG, PNG or HEIC",
                label_visibility="collapsed",
                type=["jpg", "jpeg", "png", "heic", "heif"],
                key=f"doc_upload_{epoch}",
                disabled=busy,
            )
            st.caption(tr("One page · up to 10 MB · up to 20 megapixels"))
        else:
            st.caption(tr("An original synthetic example in the selected language."))
        original = st.checkbox(
            tr("Use original framing"),
            key="doc_original",
            disabled=busy,
            help=tr("Enable this if the detected document border is wrong."),
        )
        st.button(
            tr("Clear session"),
            on_click=lambda: clear_session(state),
            disabled=busy,
            width="stretch",
        )
        st.caption(
            tr("Images are processed on this computer. No cloud OCR API or document database.")
        )
        st.caption(tr("The first use of a language may download model files."))

    data = None
    source_name = ""
    if source == "Try a sample" and language in LANGUAGES:
        try:
            data = (PROJECT_ROOT / "samples" / f"{language}.png").read_bytes()
            source_name = f"sample-{language}"
        except OSError:
            st.error(tr("The example image is missing. Upload an image instead."))
    elif uploaded is not None:
        try:
            accept_upload(getattr(uploaded, "file_id", uploaded.name), "doc_accepted_upload")
            data = uploaded.getvalue()
            source_name = uploaded.name
        except RequestLimitExceeded as error:
            st.warning(tr(str(error)))
    key = document_key(data, language, original, source_name) if data is not None else None
    sync_document(state, key)
    if data is not None and "doc_preview" not in state and not state.get("doc_error"):
        try:
            state["doc_preview"] = load_image(data)
        except (ValueError, OSError) as error:
            state["doc_error"] = str(error)
    if state.get("doc_error"):
        st.error(tr(state["doc_error"]))
    if data is None:
        st.info(tr("Upload a printed, single-column page or try a sample to get started."))
    st.button(
        tr("Scan and read text"),
        type="primary",
        on_click=queue_processing,
        disabled=data is None
        or language not in LANGUAGES
        or "doc_preview" not in state
        or state.get("doc_processing", False),
        width="stretch",
    )
    if state.pop("doc_pending", False):
        # Controls have already rendered disabled during this run. A second click
        # cannot enqueue another inference while the current intention is running.
        state.pop("doc_result", None)
        state.pop("doc_downloads", None)
        state.pop("doc_download_key", None)
        state.pop("doc_error", None)
        status = st.empty()
        try:
            reserve("ocr")
            with st.spinner(tr("Processing your document...")):
                result = process_document(
                    data,
                    language,
                    use_original=original,
                    engine_loader=load_session_engine,
                    on_progress=lambda message: status.info(tr(message)),
                )
            state["doc_result"] = result
            state["doc_edited_text"] = result.ocr.text
        except (ProcessingError, ValueError, OSError) as error:
            state["doc_error"] = str(error)
        finally:
            state["doc_processing"] = False
        st.rerun()

    result = state.get("doc_result")
    if result is None:
        if "doc_preview" in state:
            st.image(state["doc_preview"], caption=tr("Original image"), width="stretch")
        return
    for warning in result.warnings:
        st.warning(tr(warning))
    st.success(tr("Text reading complete.") if result.ocr.blocks else tr("Image processed."))
    st.caption(
        tr("Original framing retained.")
        if result.used_original
        else tr("Document border detected and perspective corrected.")
    )
    left, right = st.columns(2)
    with left:
        st.subheader(tr("Input"))
        original_tab, boundary_tab = st.tabs([tr("Original"), tr("Detected boundary")])
        with original_tab:
            st.image(result.scan.original, width="stretch")
        with boundary_tab:
            st.image(result.scan.preview, width="stretch")
    with right:
        st.subheader(tr("Scan"))
        mode = st.radio(
            tr("Scan appearance"),
            ["Color", "Black and white"],
            horizontal=True,
            format_func=option_labels(),
            key="doc_mode",
        )
        scan = result.scan.color if mode == "Color" else result.scan.monochrome
        st.image(scan, width="stretch")
    st.subheader(tr("Recognized text"))
    if not result.ocr.blocks:
        st.warning(
            tr("No text detected. Check the image quality and selected language, then retry.")
        )
    st.text_area(tr("Review and edit the text"), key="doc_edited_text", height=220)
    st.caption(tr("OCR can miss characters and punctuation. Review the text before exporting."))
    with st.expander(tr("Model confidence")):
        st.caption(
            tr(
                "These are model confidence scores, not measured accuracy. Text boxes refer to the image read by OCR."
            )
        )
        st.dataframe(
            [
                {tr("Text"): block.text, tr("Confidence"): round(block.confidence, 3)}
                for block in result.ocr.blocks
            ],
            width="stretch",
            hide_index=True,
        )
    st.subheader(tr("Download"))
    st.caption(
        tr(
            "After editing text or changing scan appearance, select Prepare downloads. The PDF contains the scan image; TXT contains your edited text."
        )
    )
    current_export = export_key(key, mode, state["doc_edited_text"])
    if st.button(tr("Prepare downloads"), width="stretch"):
        try:
            state["doc_downloads"] = {
                "png": image_bytes(scan, "PNG"),
                "pdf": image_bytes(scan, "PDF"),
                "txt": text_bytes(state["doc_edited_text"]),
            }
            state["doc_download_key"] = current_export
        except (ValueError, OSError):
            state.pop("doc_downloads", None)
            st.error(tr("Could not prepare downloads. Try again."))
    if state.get("doc_download_key") == current_export and "doc_downloads" in state:
        columns = st.columns(3)
        for column, extension, mime in zip(
            columns,
            ("png", "pdf", "txt"),
            ("image/png", "application/pdf", "text/plain; charset=utf-8"),
        ):
            with column:
                st.download_button(
                    tr("Download {kind}").format(kind=extension.upper()),
                    state["doc_downloads"][extension],
                    file_name=f"document.{extension}",
                    mime=mime,
                    on_click="ignore",
                    width="stretch",
                )
