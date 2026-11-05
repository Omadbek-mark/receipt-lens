from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from scanner import model_cache, ui

APP = Path(__file__).resolve().parents[1] / "app.py"


class FakeEngine:
    def __init__(self):
        self.calls = 0

    def predict(self, image):
        self.calls += 1
        return [
            {
                "rec_texts": ["O‘quv 한국어 English"],
                "rec_scores": [0.91],
                "rec_polys": [[[10, 10], [200, 10], [200, 40], [10, 40]]],
            }
        ]


@pytest.fixture
def models(monkeypatch):
    created = []

    def factory(language):
        engine = FakeEngine()
        created.append((language, engine))
        return engine

    monkeypatch.setattr(model_cache, "create_engine", factory)
    return created


def button(app, label):
    return next(item for item in app.button if item.label == label)


def scanner_app():
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    app.radio(key="workspace").set_value("Document scanner").run()
    return app


def sample_app():
    app = scanner_app()
    app.selectbox(key="doc_language").set_value("en").run()
    app.radio(key="doc_source").set_value("Try a sample").run()
    return app


def test_initial_screen_does_not_load_models(models):
    app = scanner_app()
    assert not app.exception
    assert button(app, "Scan and read text").disabled
    assert models == []


def test_editing_preparing_downloads_and_appearance_do_not_run_ocr_again(models):
    app = sample_app()
    button(app, "Scan and read text").click().run()
    assert not app.exception
    assert len(models) == 1 and models[0][1].calls == 1
    edited = "O‘quv tahriri\n한국어 수정"
    app.text_area(key="doc_edited_text").set_value(edited).run()
    button(app, "Prepare downloads").click().run()
    assert not app.exception
    assert app.session_state["doc_downloads"]["txt"].decode() == edited
    assert len(app.get("download_button")) == 3
    app.radio(key="doc_mode").set_value("Black and white").run()
    assert len(app.get("download_button")) == 0
    button(app, "Prepare downloads").click().run()
    assert len(app.get("download_button")) == 3
    assert models[0][1].calls == 1
    app.text_area(key="doc_edited_text").set_value("new edits").run()
    assert len(app.get("download_button")) == 0


def test_language_change_clears_results_and_models_are_reused_per_session(models):
    app = sample_app()
    button(app, "Scan and read text").click().run()
    button(app, "Scan and read text").click().run()
    assert len(models) == 1 and models[0][1].calls == 2
    app.selectbox(key="doc_language").set_value("korean").run()
    assert not app.text_area
    assert "doc_result" not in app.session_state
    button(app, "Scan and read text").click().run()
    assert [lang for lang, _ in models] == ["en", "korean"]
    assert not app.exception


def test_clear_session_removes_result_editor_upload_and_models(models):
    app = sample_app()
    button(app, "Scan and read text").click().run()
    button(app, "Clear session").click().run()
    assert not app.exception
    assert not app.text_area
    assert "doc_engines" not in app.session_state
    assert app.radio(key="doc_source").value == "Upload an image"
    assert button(app, "Scan and read text").disabled


def test_model_failure_shows_safe_error_and_allows_retry(monkeypatch):
    def broken(language):
        raise RuntimeError("internal details")

    monkeypatch.setattr(model_cache, "create_engine", broken)
    app = sample_app()
    button(app, "Scan and read text").click().run()
    assert not app.exception
    assert any("Could not load" in item.value for item in app.error)
    assert not button(app, "Scan and read text").disabled
    assert not app.text_area


def test_different_browser_sessions_do_not_share_predictors(models):
    first, second = sample_app(), sample_app()
    button(first, "Scan and read text").click().run()
    button(second, "Scan and read text").click().run()
    assert len(models) == 2
    assert models[0][1] is not models[1][1]


def test_invalid_upload_never_initializes_a_model(monkeypatch, models):
    class Upload:
        name = "broken.png"

        def getvalue(self):
            return b"not an image"

    monkeypatch.setattr(ui.st, "file_uploader", lambda *args, **kwargs: Upload())
    app = scanner_app()
    assert not app.exception
    assert app.error
    assert button(app, "Scan and read text").disabled
    assert models == []


def test_replacing_uploaded_image_removes_old_result_and_exports(monkeypatch, models):
    class Upload:
        name = "one.png"

        def getvalue(self):
            return (APP.parent / "samples/en.png").read_bytes()

    upload = Upload()
    monkeypatch.setattr(ui.st, "file_uploader", lambda *args, **kwargs: upload)
    app = scanner_app()
    app.selectbox(key="doc_language").set_value("en").run()
    button(app, "Scan and read text").click().run()
    button(app, "Prepare downloads").click().run()
    upload.name = "two.png"
    app.run()
    assert not app.exception
    assert not app.text_area and not app.get("download_button")
    assert "doc_result" not in app.session_state
    assert models[0][1].calls == 1
