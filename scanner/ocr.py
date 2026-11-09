"""CPU-only PP-OCRv5 adapter. Importing this module never downloads a model."""

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np

from scanner.layout import reading_rows

LANGUAGES = {"uz": "Uzbek (Latin)", "korean": "Korean", "en": "English"}
RECOGNIZERS = {
    "uz": "latin_PP-OCRv5_mobile_rec",
    "korean": "korean_PP-OCRv5_mobile_rec",
    "en": "en_PP-OCRv5_mobile_rec",
}
# Paddle's default only caps detection input at 4000 px, so a 12 MP phone photo peaks
# above 5 GiB and the container is OOM-killed. Capping the longest side bounds detection
# memory; recognition still crops text lines from the full-resolution image.
DETECTION_MAX_SIDE = 1920


@dataclass(frozen=True)
class TextBlock:
    text: str
    confidence: float
    polygon: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class OCRResult:
    language: str
    blocks: tuple[TextBlock, ...]

    @property
    def text(self) -> str:
        return "\n".join(" ".join(block.text for block in row) for row in reading_rows(self.blocks))


def parse_pages(pages: Iterable[Any], language: str) -> OCRResult:
    """Normalize PaddleOCR's output without depending on Paddle in unit tests."""
    blocks = []
    for page in pages:
        texts = page["rec_texts"]
        scores = page["rec_scores"]
        polygons = page["rec_polys"]
        if not (len(texts) == len(scores) == len(polygons)):
            raise ValueError("OCR returned inconsistent text, score and polygon lengths.")
        for text, score, polygon in zip(texts, scores, polygons):
            if text.strip():
                points = tuple((float(x), float(y)) for x, y in polygon)
                confidence = float(score)
                if (
                    len(points) != 4
                    or not all(math.isfinite(v) for point in points for v in point)
                    or not math.isfinite(confidence)
                    or not 0 <= confidence <= 1
                ):
                    raise ValueError("OCR returned invalid coordinates or confidence.")
                if max(y for _, y in points) <= min(y for _, y in points):
                    raise ValueError("OCR returned a text box with zero height.")
                blocks.append(TextBlock(text.strip(), confidence, points))
    ordered = tuple(block for row in reading_rows(blocks) for block in row)
    return OCRResult(language=language, blocks=ordered)


def create_engine(language: str) -> Any:
    if language not in LANGUAGES:
        raise ValueError(f"Unsupported language. Choose one of: {', '.join(LANGUAGES)}")
    # Hoster health checks run at import time, even with cached weights. Skip that
    # probe, while leaving actual first-use model downloads enabled.
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    from paddleocr import PaddleOCR

    return PaddleOCR(
        device="cpu",
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name=RECOGNIZERS[language],
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_det_limit_type="max",
        text_det_limit_side_len=DETECTION_MAX_SIDE,
        enable_mkldnn=False,
    )


def recognize(engine: Any, image: str | Path | np.ndarray, language: str) -> OCRResult:
    """Accept paths for compatibility, or RGB arrays for the in-memory pipeline.

    Paddle's ndarray reader expects BGR; convert only at this adapter boundary.
    Returned text polygons are in the pixels of the image passed to the model.
    """
    if language not in LANGUAGES:
        raise ValueError("Unsupported OCR language.")
    if isinstance(image, np.ndarray):
        if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("OCR expects an RGB uint8 image.")
        model_input = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    else:
        model_input = str(image)
    return parse_pages(engine.predict(model_input), language)
