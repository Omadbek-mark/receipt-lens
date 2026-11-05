import os
import time
from pathlib import Path

from streamlit.testing.v1 import AppTest

from scanner import model_cache
from scanner.expense_store import ExpenseStore

APP = Path(__file__).resolve().parents[1] / "app.py"
PASSWORD = "synthetic-preview-password"


def button(app, label):
    return next(item for item in app.button if item.label == label)


class ReceiptEngine:
    def predict(self, image):
        text = ["DEMO CAFE", "Date: 2026-11-01", "TOTAL: 11.00 USD"]
        return [
            {
                "rec_texts": text,
                "rec_scores": [0.9] * 3,
                "rec_polys": [
                    [[10, y], [500, y], [500, y + 30], [10, y + 30]] for y in (10, 60, 110)
                ],
            }
        ]


def signed_in(monkeypatch):
    store = ExpenseStore(Path(os.environ["SCANNER_DB_PATH"]))
    owner = store.register("receipt_demo", PASSWORD)
    monkeypatch.setattr(model_cache, "create_engine", lambda lang: ReceiptEngine())
    app = AppTest.from_file(str(APP), default_timeout=15)
    app.session_state["auth_account"] = (owner, "receipt_demo")
    app.session_state["auth_started"] = time.time()
    app.run()
    return app, store, owner


def read_sample(app):
    if app.selectbox(key="receipt_language").value is None:
        app.selectbox(key="receipt_language").set_value("en").run()
    app.radio(key="receipt_source").set_value("Try a demo receipt").run()
    button(app, "Read receipt").click().run()
    assert not app.exception


def test_guest_cannot_see_ledger_or_capture():
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    assert not app.exception
    assert not any(r.key == "receipt_section" for r in app.radio)
    assert len(app.get("file_uploader")) == 0
    assert any(item.label == "Sign in" for item in app.button)


def test_real_login_form_establishes_server_session():
    store = ExpenseStore(Path(os.environ["SCANNER_DB_PATH"]))
    owner = store.register("receipt_demo", PASSWORD)
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    app.text_input(key="login_username").set_value("receipt_demo")
    app.text_input(key="login_password").set_value(PASSWORD)
    button(app, "Sign in").click().run()
    assert not app.exception
    assert app.session_state["auth_account"][0] == owner
    assert any(r.key == "receipt_section" for r in app.radio)


def test_create_account_opens_receipt_workspace_without_sign_in():
    short_password = "abc12"
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    for label, value in (
        ("New username", " Receipt_New "),
        ("New password", short_password),
        ("Repeat password", short_password),
    ):
        next(field for field in app.text_input if field.label == label).set_value(value)
    button(app, "Create account").click().run()

    assert not app.exception
    assert app.radio(key="receipt_section").value == "Add receipt"
    store = ExpenseStore(Path(os.environ["SCANNER_DB_PATH"]))
    assert app.session_state["auth_account"] == store.authenticate("receipt_new", short_password)
    assert not any(item.label == "Sign in" for item in app.button)


def test_review_requires_confirmation_and_save_is_idempotent(monkeypatch):
    app, store, owner = signed_in(monkeypatch)
    read_sample(app)
    assert app.text_input(key="receipt_field_amount").value == "11.00"
    button(app, "Save expense").click().run()
    assert store.list(owner, "2026-01-01", "2026-12-31") == []
    app.checkbox(key="receipt_field_confirm").check()
    button(app, "Save expense").click().run()
    assert not app.exception
    assert len(store.list(owner, "2026-01-01", "2026-12-31")) == 1
    assert button(app, "Save expense").disabled
    app.radio(key="receipt_section").set_value("My expenses").run()
    assert not app.exception
    assert len(app.get("download_button")) == 1


def test_input_changes_and_signout_remove_private_draft(monkeypatch):
    app, store, owner = signed_in(monkeypatch)
    read_sample(app)
    app.selectbox(key="receipt_language").set_value("korean").run()
    assert "receipt_result" not in app.session_state
    assert not any(item.key == "receipt_field_amount" for item in app.text_input)
    read_sample(app)
    button(app, "Sign out").click().run()
    assert not app.exception
    assert "auth_account" not in app.session_state
    assert "receipt_result" not in app.session_state
    assert "doc_engines" not in app.session_state


def test_ledger_delete_requires_explicit_confirmation(monkeypatch):
    app, store, owner = signed_in(monkeypatch)
    read_sample(app)
    app.checkbox(key="receipt_field_confirm").check()
    button(app, "Save expense").click().run()
    app.radio(key="receipt_section").set_value("My expenses").run()
    assert button(app, "Delete expense").disabled
    next(c for c in app.checkbox if c.label.startswith("Delete this expense")).check().run()
    button(app, "Delete expense").click().run()
    assert not app.exception
    assert store.list(owner, "2026-01-01", "2026-12-31") == []


def test_builtin_table_csv_also_neutralizes_formula_cells(monkeypatch):
    app, store, owner = signed_in(monkeypatch)
    read_sample(app)
    app.text_input(key="receipt_field_merchant").set_value("=TEST()")
    app.text_area(key="receipt_field_note").set_value("\t@TEST()")
    app.checkbox(key="receipt_field_confirm").check()
    button(app, "Save expense").click().run()
    app.radio(key="receipt_section").set_value("My expenses").run()
    assert not app.exception
    table = app.dataframe[-1].value
    assert table.iloc[0]["Merchant"] == "'=TEST()"
    assert table.iloc[0]["Note"].startswith("'@")  # input is trimmed on save


def test_receipt_language_is_required_and_manual_crop_does_not_run_ocr(monkeypatch):
    app, store, owner = signed_in(monkeypatch)
    assert app.selectbox(key="receipt_language").value is None
    app.radio(key="receipt_source").set_value("Try a demo receipt").run()
    assert button(app, "Read receipt").disabled
    app.selectbox(key="receipt_language").set_value("korean").run()
    app.radio(key="receipt_framing").set_value("Manual crop").run()
    next(s for s in app.slider if s.label == "Horizontal crop (%)").set_value((10, 90)).run()
    assert "receipt_result" not in app.session_state
    button(app, "Read receipt").click().run()
    assert not app.exception
    assert app.session_state["receipt_result"].scan.crop_box == (100, 0, 900, 1200)


def test_translation_is_disabled_until_server_setup(monkeypatch):
    from scanner import translation_ui

    monkeypatch.setattr(translation_ui, "configured_key", lambda: "")
    app, store, owner = signed_in(monkeypatch)
    read_sample(app)
    assert button(app, "Translate text").disabled
    assert any("not available" in message.value for message in app.info)


def test_translation_needs_consent_and_never_changes_saved_source(monkeypatch):
    from scanner import translation_ui

    calls = []
    monkeypatch.setattr(translation_ui, "configured_key", lambda: "fake-test-key")

    def translate(lines, source, target, key):
        calls.append((lines, source, target))
        return ["Tarjima: " + line for line in lines]

    monkeypatch.setattr(translation_ui, "translate_lines", translate)
    app, store, owner = signed_in(monkeypatch)
    read_sample(app)
    original = app.session_state["receipt_result"].ocr.text
    app.selectbox(key="receipt_translation_target").set_value("uz").run()
    assert button(app, "Translate text").disabled
    next(c for c in app.checkbox if c.label.startswith("Send this text")).check().run()
    button(app, "Translate text").click().run()
    assert not app.exception and len(calls) == 1
    assert app.session_state["receipt_result"].ocr.text == original
    assert app.text_input(key="receipt_field_amount").value == "11.00"
    assert button(app, "Translate text").disabled


def test_old_implicit_english_selection_is_cleared_on_upgrade():
    store = ExpenseStore(Path(os.environ["SCANNER_DB_PATH"]))
    owner = store.register("receipt_demo", PASSWORD)
    app = AppTest.from_file(str(APP), default_timeout=15)
    app.session_state["auth_account"] = (owner, "receipt_demo")
    app.session_state["auth_started"] = time.time()
    app.session_state["receipt_language"] = "en"
    app.run()
    assert not app.exception
    assert app.selectbox(key="receipt_language").value is None


def test_interface_language_switch_preserves_receipt_result_and_source_language(monkeypatch):
    app, _, _ = signed_in(monkeypatch)
    app.selectbox(key="receipt_language").set_value("korean").run()
    read_sample(app)

    app.selectbox(key="ui_language").set_value("uz").run()
    assert not app.exception
    assert app.radio(key="receipt_source").value == "Try a demo receipt"
    assert app.selectbox(key="receipt_language").value == "korean"
    assert app.session_state["receipt_result"].ocr.language == "korean"
    assert app.text_input(key="receipt_field_amount").label == "Jami summa"

    app.selectbox(key="ui_language").set_value("ko").run()
    assert not app.exception
    assert app.selectbox(key="receipt_language").value == "korean"
    assert app.session_state["receipt_result"].ocr.language == "korean"
    assert app.text_input(key="receipt_field_amount").label == "합계 금액"

    app.radio(key="workspace").set_value("Document scanner").run()
    assert not app.exception
    assert app.selectbox(key="doc_language").label == "문서 언어"
