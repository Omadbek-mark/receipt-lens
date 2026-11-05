from math import cos, sin

import numpy as np
import pytest

from scanner.imaging import scan_document
from scanner.layout import aligned_text, display_width, reading_rows
from scanner.ocr import OCRResult, TextBlock


def block(text, x, y, width, height=20, angle=0):
    points = [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]
    return TextBlock(
        text,
        0.9,
        tuple(
            (px * cos(angle) - py * sin(angle), px * sin(angle) + py * cos(angle))
            for px, py in points
        ),
    )


def test_tilted_receipt_columns_join_the_correct_line():
    blocks = [
        block("10,000", 250, 50, 60, angle=0.17),
        block("상품", 10, 50, 40, angle=0.17),
        block("합계", 10, 90, 40, angle=0.17),
        block("20,000", 250, 90, 60, angle=0.17),
    ]
    assert [[b.text for b in row] for row in reading_rows(blocks)] == [
        ["상품", "10,000"],
        ["합계", "20,000"],
    ]
    assert OCRResult("korean", tuple(blocks)).text == "상품 10,000\n합계 20,000"
    lines = aligned_text(blocks).splitlines()
    assert lines[0].index("10,000") == lines[1].index("20,000")
    assert "상품  " in lines[0]


def test_hangul_column_width_and_adjacent_lines_are_preserved():
    assert display_width("한국어") == 6
    assert display_width("e\u0301") == 1
    blocks = [
        block("한국어", 0, 0, 60),
        block("100", 200, 0, 30),
        block("ABCDEF", 0, 40, 60),
        block("200", 200, 40, 30),
    ]
    text = aligned_text(blocks).splitlines()
    assert display_width(text[0].split("100")[0]) == display_width(text[1].split("200")[0])
    assert len(reading_rows(blocks)) == 2


def test_empty_layout_and_no_word_loss_on_overlap():
    assert reading_rows([]) == [] and aligned_text([]) == ""
    text = aligned_text([block("long word", 0, 0, 20), block("next", 15, 0, 20)])
    assert "long word" in text and "next" in text


def test_manual_crop_uses_the_selected_pixels_and_keeps_source_coordinates():
    image = np.zeros((200, 300, 3), np.uint8)
    image[40:160, 60:240] = (200, 100, 50)
    result = scan_document(image, crop_box=(60, 40, 240, 160))
    assert result.crop_box == (60, 40, 240, 160) and not result.used_original
    assert result.color.shape == (120, 180, 3)
    assert result.color[30, 30].tolist() == [200, 100, 50]
    assert result.original.shape == image.shape and result.warning is None


@pytest.mark.parametrize(
    "crop",
    [(-1, 0, 100, 100), (0, 0, 500, 500), (0, 0, 10, 10), (10, 10, 5, 5), (0.5, 0, 100, 100)],
)
def test_invalid_manual_crops_are_rejected(crop):
    with pytest.raises(ValueError):
        scan_document(np.zeros((200, 300, 3), np.uint8), crop_box=crop)


def test_original_framing_and_manual_crop_are_mutually_exclusive():
    with pytest.raises(ValueError):
        scan_document(
            np.zeros((200, 300, 3), np.uint8), crop_box=(0, 0, 100, 100), use_original=True
        )
