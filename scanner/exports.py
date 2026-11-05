"""In-memory scan exports. PDFs contain an image, not an OCR text layer."""

from io import BytesIO

import numpy as np
from PIL import Image


def image_bytes(image: np.ndarray, file_format: str) -> bytes:
    if file_format not in {"PNG", "PDF"}:
        raise ValueError("Choose PNG or PDF.")
    output = BytesIO()
    picture = Image.fromarray(image)
    if file_format == "PDF":
        picture = picture.convert("RGB")
        picture.save(output, format="PDF", resolution=150.0)
    else:
        picture.save(output, format="PNG")
    return output.getvalue()


def text_bytes(text: str) -> bytes:
    return text.encode("utf-8")
