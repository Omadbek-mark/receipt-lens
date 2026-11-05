"""Account-protected personal receipt review and expense ledger."""

import sqlite3
import time
from datetime import date
from hashlib import sha256
from io import BytesIO

import streamlit as st
from PIL import Image

from scanner.accounts import normalize_username
from scanner.crop_ui import manual_crop
from scanner.expense_reports import expense_csv, safe_csv_cell, summaries
from scanner.expense_store import DuplicateReceipt, ExpenseStore
from scanner.i18n import option_labels, tr
from scanner.model_cache import load_session_engine
from scanner.ocr import LANGUAGES
from scanner.ocr_view import render_ocr_view
from scanner.pipeline import ProcessedDocument, ProcessingError, process_document
from scanner.receipts import CATEGORIES, CURRENCIES, extract_receipt, format_amount, parse_amount
from scanner.session import clear_session
from scanner.settings import APP_NAME, PROJECT_ROOT, database_path
from scanner.translation_ui import render_translation


def sign_out() -> None:
    clear_session(st.session_state)
    for name in list(st.session_state):
        if name.startswith(("receipt_", "auth_")):
            del st.session_state[name]


def get_store() -> ExpenseStore:
    return ExpenseStore(database_path())


def account_gate(store: ExpenseStore) -> tuple[str, str] | None:
    state = st.session_state
    account = state.get("auth_account")
    if account and (
        time.time() - state.get("auth_started", 0) > 8 * 3600 or not store.user_exists(account[0])
    ):
        sign_out()
        account = None
    if account:
        with st.sidebar:
            st.caption(tr("Signed in as {username}").format(username=account[1]))
            st.button(tr("Sign out"), on_click=sign_out, disabled=state.get("receipt_busy", False))
        return account
    st.caption(
        tr(
            "Sign in to save reviewed receipts and view your own expenses. Scanner-only mode is also available."
        )
    )
    login, register = st.tabs([tr("Sign in"), tr("Create account")])
    with login:
        with st.form("auth_login", clear_on_submit=True):
            username = st.text_input(tr("Username"), key="login_username", max_chars=32)
            password = st.text_input(
                tr("Password"), type="password", key="login_password", max_chars=128
            )
            submitted = st.form_submit_button(tr("Sign in"))
        if submitted:
            try:
                account = store.authenticate(username, password)
                if account:
                    state["auth_account"] = account
                    state["auth_started"] = time.time()
                    st.rerun()
                st.error(tr("Username or password was not accepted."))
            except ValueError as error:
                st.error(tr(str(error)))
    with register:
        st.caption(
            tr(
                "Use a new username and a password of 5–128 characters. This local preview has no password-reset email."
            )
        )
        with st.form("auth_register", clear_on_submit=True):
            username = st.text_input(tr("New username"), max_chars=32)
            password = st.text_input(tr("New password"), type="password", max_chars=128)
            confirm = st.text_input(tr("Repeat password"), type="password", max_chars=128)
            submitted = st.form_submit_button(tr("Create account"))
        if submitted:
            try:
                if password != confirm:
                    raise ValueError("Passwords must match.")
                username = normalize_username(username)
                owner = store.register(username, password)
                state["auth_account"] = (owner, username)
                state["auth_started"] = time.time()
                st.rerun()
            except ValueError as error:
                st.error(tr(str(error)))
    return None


def request_receipt() -> None:
    if not st.session_state.get("receipt_busy"):
        st.session_state["receipt_busy"] = True
        st.session_state["receipt_pending"] = True


def reset_draft() -> None:
    for name in list(st.session_state):
        if name.startswith(
            (
                "receipt_field_",
                "receipt_result",
                "receipt_proposal",
                "receipt_saved",
                "receipt_error",
                "receipt_translation",
            )
        ):
            del st.session_state[name]


def render_review(store: ExpenseStore, owner: str, data: bytes, result: ProcessedDocument) -> None:
    state = st.session_state
    if "receipt_proposal" not in state:
        state["receipt_proposal"] = extract_receipt(result.ocr.text)
    proposal = state["receipt_proposal"]
    for warning in result.warnings:
        st.warning(tr(warning))
    st.subheader(tr("Review before saving"))
    st.caption(
        tr(
            "OCR uses AI. Field and category suggestions use rules and may be wrong. Nothing is saved until you confirm."
        )
    )
    render_ocr_view(
        result, "receipt_lines_" + sha256(state["receipt_key"].encode()).hexdigest()[:16]
    )
    render_translation(result, state["receipt_key"])
    with st.expander(tr("Evidence for field suggestions")):
        for field, evidence in proposal.evidence.items():
            label = {
                "merchant": "Merchant",
                "purchased_on": "Date",
                "amount": "Amount",
                "currency": "Currency",
            }[field]
            st.write(
                f"{tr(label)}: {tr(evidence) if evidence == 'Explicit currency marker in receipt text.' else evidence}"
            )
        for warning in proposal.warnings:
            st.caption(tr(warning))
    st.subheader(tr("Confirm expense fields"))
    with st.container():
        already_saved = store.has_image(owner, data)
        if already_saved:
            st.info(tr("This image has already been saved in your account."))
        with st.form("receipt_review"):
            merchant = st.text_input(
                tr("Merchant / organization"),
                value=proposal.merchant or "",
                key="receipt_field_merchant",
                max_chars=160,
            )
            purchased = st.text_input(
                tr("Receipt date (YYYY-MM-DD)"),
                value=proposal.purchased_on or "",
                key="receipt_field_date",
            )
            amount = st.text_input(
                tr("Total amount"), value=proposal.amount or "", key="receipt_field_amount"
            )
            currencies = ["Choose currency", *CURRENCIES]
            currency = st.selectbox(
                tr("Currency"),
                currencies,
                index=currencies.index(proposal.currency) if proposal.currency else 0,
                format_func=option_labels(),
                key="receipt_field_currency",
            )
            category = st.selectbox(
                tr("Category"),
                CATEGORIES,
                index=CATEGORIES.index(proposal.category),
                format_func=option_labels(),
                key="receipt_field_category",
            )
            note = st.text_area(tr("Note (optional)"), max_chars=1000, key="receipt_field_note")
            confirmed = st.checkbox(
                tr("I checked the merchant, date, amount and currency."),
                key="receipt_field_confirm",
            )
            similar_ok = st.checkbox(
                tr("If a similar expense exists, save this as a separate purchase."),
                key="receipt_field_similar",
            )
            st.caption(
                tr(
                    "Saving stores the image, OCR text and confirmed fields in your account. You can delete the entry from My expenses."
                )
            )
            save = st.form_submit_button(
                tr("Save expense"), disabled=already_saved or state.get("receipt_busy", False)
            )
        if save:
            try:
                if not confirmed:
                    raise ValueError("Check the receipt fields and confirm before saving.")
                minor = parse_amount(amount, currency)
                if store.similar(owner, merchant, purchased, minor, currency) and not similar_ok:
                    raise ValueError(
                        "A matching merchant/date/amount already exists. Check it, or confirm this is a separate purchase."
                    )
                # Store a compact, metadata-free copy rather than EXIF/location metadata.
                picture = Image.fromarray(result.scan.original)
                picture.thumbnail((2048, 2048))
                encoded = BytesIO()
                picture.save(encoded, "JPEG", quality=90)
                store.save(
                    owner,
                    merchant=merchant,
                    purchased_on=purchased,
                    amount=amount,
                    currency=currency,
                    category=category,
                    note=note,
                    source=data,
                    image=encoded.getvalue(),
                    ocr_text=result.ocr.text,
                )
                state["receipt_saved"] = True
                st.rerun()
            except (ValueError, DuplicateReceipt) as error:
                st.error(tr(str(error)))
    if state.get("receipt_saved"):
        st.success(tr("Expense saved. Open My expenses to view it."))


def render_capture(store: ExpenseStore, owner: str) -> None:
    state = st.session_state
    busy = state.get("receipt_busy", False)
    source = st.radio(
        tr("Receipt source"),
        ["Upload a receipt", "Try a demo receipt"],
        format_func=option_labels(),
        key="receipt_source",
        disabled=busy,
    )
    if not state.get("receipt_explicit_language_v2"):
        state["receipt_language"] = None
        state["receipt_explicit_language_v2"] = True
    language = st.selectbox(
        tr("Language printed on receipt"),
        list(LANGUAGES),
        index=None,
        placeholder=tr("Choose the language printed on the receipt"),
        format_func=option_labels(LANGUAGES),
        key="receipt_language",
        disabled=busy,
        help=tr(
            "Choose the original receipt language. To translate it, use Translate receipt text after OCR."
        ),
    )
    data = None
    if source == "Try a demo receipt" and language in LANGUAGES:
        sample_name = "korean-layout.png" if language == "korean" else f"{language}.png"
        data = (PROJECT_ROOT / "samples/receipts" / sample_name).read_bytes()
    elif source == "Upload a receipt":
        st.caption(tr("Receipt JPEG, PNG or HEIC"))
        uploaded = st.file_uploader(
            "Receipt JPEG, PNG or HEIC",
            label_visibility="collapsed",
            type=["jpg", "jpeg", "png", "heic", "heif"],
            key="receipt_upload",
            disabled=busy,
        )
        if uploaded is not None:
            data = uploaded.getvalue()
    framing = st.radio(
        tr("Receipt framing"),
        ["Automatic", "Original", "Manual crop"],
        horizontal=True,
        format_func=option_labels(),
        key="receipt_framing",
        disabled=busy,
    )
    original = framing == "Original"
    crop_box, crop_valid = (None, True)
    if framing == "Manual crop" and data is not None:
        crop_box, crop_valid = manual_crop(data, "receipt", busy)
    if language is None:
        st.info(tr("Choose Korean for a Korean receipt. No language model is selected by default."))
    key = (
        sha256(data).hexdigest() + str(language) + str(original) + str(crop_box)
        if data is not None
        else None
    )
    if state.get("receipt_key") != key:
        reset_draft()
        state["receipt_key"] = key
        state["receipt_busy"] = False
        state["receipt_pending"] = False
    st.caption(tr("One receipt · JPEG/PNG/HEIC · up to 10 MB and 20 megapixels"))
    st.button(
        tr("Read receipt"),
        type="primary",
        disabled=data is None
        or language not in LANGUAGES
        or not crop_valid
        or state.get("receipt_busy", False),
        on_click=request_receipt,
    )
    if state.pop("receipt_pending", False):
        reset_draft()
        progress = st.empty()
        try:
            with st.spinner(tr("Reading your receipt...")):
                state["receipt_result"] = process_document(
                    data,
                    language,
                    use_original=original,
                    crop_box=crop_box,
                    engine_loader=load_session_engine,
                    on_progress=lambda message: progress.info(tr(message)),
                )
        except (ProcessingError, ValueError, OSError) as error:
            state["receipt_error"] = str(error)
        finally:
            state["receipt_busy"] = False
        st.rerun()
    if state.get("receipt_error"):
        st.error(tr(state["receipt_error"]))
    if "receipt_result" in state and data is not None:
        render_review(store, owner, data, state["receipt_result"])


def render_ledger(store: ExpenseStore, owner: str) -> None:
    st.subheader(tr("My expenses"))
    st.caption(
        tr(
            "Dates come from reviewed receipts. Amounts in different currencies are never combined or converted."
        )
    )
    today = date.today()
    start_column, end_column, category_column = st.columns(3)
    with start_column:
        start = st.date_input(tr("From"), value=today.replace(day=1), key="receipt_filter_start")
    with end_column:
        end = st.date_input(tr("To"), value=today, key="receipt_filter_end")
    with category_column:
        category = st.selectbox(
            tr("Filter category"),
            ["All", *CATEGORIES],
            format_func=option_labels(),
            key="receipt_filter_category",
        )
    try:
        rows = store.list(
            owner, start.isoformat(), end.isoformat(), None if category == "All" else category
        )
    except ValueError as error:
        st.error(tr(str(error)))
        return
    if not rows:
        st.info(tr("No expenses match these filters. Adjust the dates or save a reviewed receipt."))
        return
    totals, months = summaries(rows)
    st.write(tr("Totals for the selected filters"))
    st.dataframe(
        [{tr(key): value for key, value in row.items()} for row in totals],
        hide_index=True,
        width="stretch",
    )
    st.write(tr("Monthly totals for the selected filters"))
    st.dataframe(
        [{tr(key): value for key, value in row.items()} for row in months],
        hide_index=True,
        width="stretch",
    )
    # Streamlit tables also have a built-in CSV download. Protect its cells too,
    # rather than protecting only the dedicated export button.
    display = [
        {
            tr("Date"): r["purchased_on"],
            tr("Merchant"): safe_csv_cell(r["merchant"]),
            tr("Amount"): format_amount(r["amount_minor"], r["currency"]),
            tr("Currency"): r["currency"],
            tr("Category"): tr(r["category"]),
            tr("Note"): safe_csv_cell(r["note"]),
        }
        for r in rows
    ]
    st.dataframe(display, hide_index=True, width="stretch")
    st.download_button(
        tr("Export filtered CSV"),
        expense_csv(rows),
        "expenses.csv",
        "text/csv; charset=utf-8",
        on_click="ignore",
    )
    selected = st.selectbox(
        tr("View saved receipt"),
        [r["id"] for r in rows],
        format_func=lambda identifier: next(
            f"{r['purchased_on']} · {r['merchant']} · {format_amount(r['amount_minor'], r['currency'])} {r['currency']}"
            for r in rows
            if r["id"] == identifier
        ),
    )
    record = store.get(owner, selected)
    if record:
        with st.expander(tr("Saved image and OCR text")):
            st.image(record["image"], width="stretch")
            st.text(record["ocr_text"])
        confirmation = st.checkbox(
            tr("Delete this expense and its saved receipt image."), key=f"receipt_delete_{selected}"
        )
        if st.button(tr("Delete expense"), disabled=not confirmation):
            store.delete(owner, selected)
            st.rerun()


def render_expenses() -> None:
    st.title(APP_NAME)
    st.caption(tr("Read a receipt, check the fields, and keep a personal expense record."))
    try:
        store = get_store()
        account = account_gate(store)
        if account is None:
            return
        section = st.radio(
            tr("Expense workspace"),
            ["Add receipt", "My expenses"],
            horizontal=True,
            format_func=option_labels(),
            key="receipt_section",
            disabled=st.session_state.get("receipt_busy", False),
        )
        if section == "Add receipt":
            render_capture(store, account[0])
        else:
            render_ledger(store, account[0])
    except (sqlite3.Error, OSError):
        st.error(tr("Expense storage is unavailable. Check the local data directory and retry."))
