from io import BytesIO

import numpy as np
import pypdfium2
import pytest
from PIL import Image

from scanner.exports import image_bytes, text_bytes
from scanner.session import clear_session, document_key, export_key, sync_document


def test_png_is_lossless_and_pdf_has_one_correctly_proportioned_image_page():
    image = np.full((300, 600, 3), (240, 220, 190), np.uint8)
    image[50:150, 100:200] = (20, 60, 90)
    png = image_bytes(image, "PNG")
    assert np.array_equal(np.array(Image.open(BytesIO(png))), image)
    pdf = pypdfium2.PdfDocument(image_bytes(image, "PDF"))
    assert len(pdf) == 1
    page = pdf[0]
    assert page.get_width() / page.get_height() == pytest.approx(2)
    bitmap = page.render(scale=1)
    rendered = np.array(bitmap.to_pil())
    assert rendered.shape[1] / rendered.shape[0] == pytest.approx(2, abs=0.02)
    bitmap.close()
    page.close()
    pdf.close()


def test_grayscale_exports_and_edited_unicode_text():
    image = np.full((100, 200), 255, np.uint8)
    assert image_bytes(image, "PDF").startswith(b"%PDF")
    assert Image.open(BytesIO(image_bytes(image, "PNG"))).mode == "L"
    edited = "O‘quv markazi\n한국어 수정\nEnglish edited text"
    assert text_bytes(edited).decode("utf-8") == edited


@pytest.mark.parametrize("change", ["content", "language", "framing", "filename"])
def test_changed_document_identity_discards_stale_result_and_downloads(change):
    args = [b"image", "en", False, "one.png"]
    old = document_key(*args)
    state = {
        "doc_active_key": old,
        "doc_result": object(),
        "doc_edited_text": "old",
        "doc_downloads": {"txt": b"old"},
        "doc_preview": object(),
        "doc_engines": {"en": object()},
    }
    index, value = {
        "content": (0, b"new"),
        "language": (1, "uz"),
        "framing": (2, True),
        "filename": (3, "two.png"),
    }[change]
    args[index] = value
    assert sync_document(state, document_key(*args))
    assert "doc_result" not in state and "doc_downloads" not in state
    assert "doc_edited_text" not in state and "doc_preview" not in state
    assert "doc_engines" in state  # reused only within the same browser session


def test_unchanged_input_keeps_edited_text_and_clear_drops_model_references():
    state = {
        "doc_active_key": "same",
        "doc_edited_text": "edited",
        "doc_engines": {"en": object()},
        "doc_upload_epoch": 2,
        "unrelated": 1,
    }
    assert not sync_document(state, "same")
    assert state["doc_edited_text"] == "edited"
    clear_session(state)
    assert state == {"doc_upload_epoch": 3, "unrelated": 1}


def test_export_identity_includes_text_and_scan_appearance():
    assert export_key("doc", "Color", "a") != export_key("doc", "Color", "b")
    assert export_key("doc", "Color", "a") != export_key("doc", "Black and white", "a")
