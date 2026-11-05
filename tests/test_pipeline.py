import json
import sys
from io import BytesIO

import numpy as np
import pytest
from PIL import Image, ImageDraw

from scanner import pipeline
from scanner.ocr import parse_pages, recognize
from scanner.pipeline import ProcessingError, process_document


def image_bytes(document=True):
    image = Image.new("RGB", (600, 500), (50, 60, 70) if document else "white")
    if document:
        ImageDraw.Draw(image).polygon([(100, 50), (500, 80), (520, 440), (70, 420)], fill="white")
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


class FakeEngine:
    def __init__(self, text="Document text"):
        self.text = text
        self.images = []

    def predict(self, image):
        self.images.append(image.copy() if isinstance(image, np.ndarray) else image)
        return [
            {
                "rec_texts": [self.text] if self.text else [],
                "rec_scores": [0.9] if self.text else [],
                "rec_polys": [[[10, 10], [150, 10], [150, 35], [10, 35]]] if self.text else [],
            }
        ]


def test_pipeline_reads_rectified_color_and_declares_coordinate_space():
    engine = FakeEngine("O‘quv 한국어")
    stages = []
    result = process_document(image_bytes(), "uz", engine=engine, on_progress=stages.append)
    assert result.scan.detected and not result.used_original
    assert engine.images[0].shape == result.scan.color.shape
    assert result.scan.color.shape != result.scan.original.shape
    assert engine.images[0].ndim == 3  # not the black-and-white export
    assert stages == ["Preparing document", "Reading document text"]
    payload = result.to_payload()
    assert payload["ocr_image"]["block_coordinate_space"] == "ocr_image"
    assert payload["scan"]["corner_coordinate_space"] == "exif_oriented_original"
    assert payload["ocr_image"]["width"] == result.scan.color.shape[1]
    assert json.loads(json.dumps(payload, ensure_ascii=False))["text"] == "O‘quv 한국어"
    assert payload["blocks"][0]["confidence"] == 0.9
    assert all(
        payload[key] >= 0 for key in ("scan_seconds", "initialization_seconds", "inference_seconds")
    )


@pytest.mark.parametrize("document,override", [(False, False), (True, True)])
def test_fallback_and_override_read_full_original(document, override):
    engine = FakeEngine()
    result = process_document(image_bytes(document), "en", use_original=override, engine=engine)
    assert result.used_original
    assert engine.images[0].shape == result.scan.original.shape
    assert bool(result.warnings) == (not document)


def test_model_is_loaded_only_after_input_validation(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid input must not initialize a model")

    monkeypatch.setattr(pipeline, "create_engine", unexpected)
    for source, language in ((b"invalid", "en"), (image_bytes(), "invalid")):
        with pytest.raises(ValueError):
            process_document(source, language)


def test_model_loading_failure_has_safe_distinct_message(monkeypatch):
    def broken(language):
        raise RuntimeError("private internal data")

    monkeypatch.setattr(pipeline, "create_engine", broken)
    with pytest.raises(ProcessingError) as raised:
        process_document(image_bytes(), "en")
    assert raised.value.stage == "model_loading"
    assert "private" not in str(raised.value)
    assert "download" in str(raised.value)


def test_inference_failure_has_distinct_message():
    class BrokenEngine:
        def predict(self, image):
            raise RuntimeError("private internal data")

    with pytest.raises(ProcessingError) as raised:
        process_document(image_bytes(), "en", engine=BrokenEngine())
    assert raised.value.stage == "recognition"
    assert "private" not in str(raised.value)


def test_empty_ocr_is_valid_result_not_a_model_error():
    result = process_document(image_bytes(False), "en", engine=FakeEngine(""))
    assert result.ocr.text == ""
    assert result.ocr.blocks == ()


def test_model_initialization_progress_and_engine_reuse(monkeypatch):
    engine = FakeEngine()
    calls = []
    stages = []
    monkeypatch.setattr(
        pipeline, "create_engine", lambda language: calls.append(language) or engine
    )
    process_document(image_bytes(), "korean", on_progress=stages.append)
    process_document(image_bytes(), "korean", engine=engine)
    assert calls == ["korean"]
    assert len(engine.images) == 2
    assert stages == ["Preparing document", "Loading OCR model", "Reading document text"]


def test_rgb_array_is_converted_to_bgr_once_without_mutating_input():
    image = np.full((40, 50, 3), (240, 100, 20), np.uint8)
    engine = FakeEngine()
    recognize(engine, image, "en")
    assert engine.images[0][0, 0].tolist() == [20, 100, 240]
    assert image[0, 0].tolist() == [240, 100, 20]


def test_path_input_remains_supported():
    engine = FakeEngine()
    recognize(engine, "sample.png", "en")
    assert engine.images == ["sample.png"]


def test_same_line_fragments_are_ordered_left_to_right_despite_y_jitter():
    result = parse_pages(
        [
            {
                "rec_texts": ["right", "next", "left"],
                "rec_scores": [0.9] * 3,
                "rec_polys": [
                    [[100, 10], [160, 10], [160, 30], [100, 30]],
                    [[10, 60], [60, 60], [60, 80], [10, 80]],
                    [[10, 13], [60, 13], [60, 33], [10, 33]],
                ],
            }
        ],
        "en",
    )
    assert result.text == "left right\nnext"


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -1, 1.1])
def test_invalid_confidence_is_rejected(score):
    with pytest.raises(ValueError, match="invalid"):
        parse_pages(
            [
                {
                    "rec_texts": ["word"],
                    "rec_scores": [score],
                    "rec_polys": [[[0, 0], [10, 0], [10, 10], [0, 10]]],
                }
            ],
            "en",
        )


def test_cli_saves_matching_scan_and_ocr_metadata(tmp_path, monkeypatch, capsys):
    from scanner import __main__ as cli

    source = tmp_path / "source.png"
    source.write_bytes(image_bytes())
    output = tmp_path / "result.json"
    preview = tmp_path / "preview"
    monkeypatch.setattr(
        cli,
        "process_document",
        lambda *args, **kwargs: process_document(*args, **kwargs, engine=FakeEngine()),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scanner",
            str(source),
            "--lang",
            "en",
            "--output",
            str(output),
            "--scan-output-dir",
            str(preview),
        ],
    )
    assert cli.main() == 0
    payload = json.loads(output.read_text())
    assert payload["text"] == "Document text"
    assert (preview / "scan-color.png").is_file()
    assert "Reading document" in capsys.readouterr().err


def test_cli_rejects_overwriting_input_before_model_load(tmp_path, monkeypatch):
    from scanner import __main__ as cli

    source = tmp_path / "source.png"
    content = image_bytes()
    source.write_bytes(content)
    monkeypatch.setattr(
        sys, "argv", ["scanner", str(source), "--lang", "en", "--output", str(source)]
    )
    with pytest.raises(SystemExit):
        cli.main()
    assert source.read_bytes() == content


def test_cli_model_failure_does_not_write_success_outputs(tmp_path, monkeypatch, capsys):
    from scanner import __main__ as cli

    source = tmp_path / "source.png"
    source.write_bytes(image_bytes())
    output = tmp_path / "result.json"

    def fail(*args, **kwargs):
        raise ProcessingError("recognition", "Could not read the document.")

    monkeypatch.setattr(cli, "process_document", fail)
    monkeypatch.setattr(
        sys, "argv", ["scanner", str(source), "--lang", "en", "--output", str(output)]
    )
    assert cli.main() == 1
    assert not output.exists()
    assert "Processing failed" in capsys.readouterr().err
