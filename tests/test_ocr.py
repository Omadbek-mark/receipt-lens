import sys
from types import SimpleNamespace

import pytest

from scanner.ocr import create_engine, parse_pages


def test_multilingual_output_preserves_unicode_and_orders_lines():
    result = parse_pages(
        [
            {
                "rec_texts": ["한국어", "O‘quv g‘oyalari", "  "],
                "rec_scores": [0.95, 0.9, 0.8],
                "rec_polys": [
                    [(0, 50), (100, 50), (100, 70), (0, 70)],
                    [(0, 10), (100, 10), (100, 30), (0, 30)],
                    [(0, 90), (100, 90), (100, 100), (0, 100)],
                ],
            }
        ],
        "uz",
    )
    assert result.text == "O‘quv g‘oyalari\n한국어"
    assert result.blocks[0].confidence == 0.9
    assert result.blocks[1].polygon[0] == (0.0, 50.0)


def test_empty_page_is_valid():
    result = parse_pages([{"rec_texts": [], "rec_scores": [], "rec_polys": []}], "en")
    assert result.text == ""
    assert result.blocks == ()


def test_inconsistent_model_output_is_not_silently_truncated():
    with pytest.raises(ValueError, match="inconsistent"):
        parse_pages([{"rec_texts": ["word"], "rec_scores": [], "rec_polys": []}], "en")


def test_invalid_language_is_rejected_before_loading_model():
    with pytest.raises(ValueError, match="Unsupported language"):
        create_engine("invalid")


@pytest.mark.parametrize(
    "language,recognizer",
    [
        ("uz", "latin_PP-OCRv5_mobile_rec"),
        ("korean", "korean_PP-OCRv5_mobile_rec"),
        ("en", "en_PP-OCRv5_mobile_rec"),
    ],
)
def test_language_selects_explicit_recognizer(monkeypatch, language, recognizer):
    monkeypatch.setitem(
        sys.modules, "paddleocr", SimpleNamespace(PaddleOCR=lambda **kwargs: kwargs)
    )
    config = create_engine(language)
    assert config["text_recognition_model_name"] == recognizer
    assert config["text_detection_model_name"] == "PP-OCRv5_mobile_det"
    assert config["device"] == "cpu"
    # PaddleOCR ignores lang when explicit model names are supplied.
    assert "lang" not in config
