from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from scanner import imaging
from scanner.imaging import load_image
from scanner.pipeline import process_document


def heif(image, **kwargs):
    buffer = BytesIO()
    image.save(buffer, format="HEIF", quality=100, **kwargs)
    return buffer.getvalue()


def test_heic_bytes_decode_as_rgb_and_work_in_pipeline():
    source = heif(Image.new("RGB", (120, 80), (220, 60, 30)))
    rgb = load_image(source)
    assert rgb.shape == (80, 120, 3) and rgb.dtype == np.uint8
    assert np.max(np.abs(rgb[40, 60].astype(int) - [220, 60, 30])) < 8

    class EmptyEngine:
        def predict(self, image):
            assert image.shape == rgb.shape
            return [{"rec_texts": [], "rec_scores": [], "rec_polys": []}]

    result = process_document(source, "en", engine=EmptyEngine())
    assert result.used_original and result.ocr.text == ""


def test_heic_orientation_is_not_applied_twice():
    image = Image.new("RGB", (80, 40), "white")
    exif = image.getexif()
    exif[274] = 6
    result = load_image(heif(image, exif=exif))
    # HEIF encoder/container transforms are normalized by the decoder; the
    # original EXIF=6 is exposed as info only and must not be reapplied.
    assert result.shape == (40, 80, 3)


def test_heic_limits_and_corruption_are_rejected(monkeypatch):
    source = heif(Image.new("RGB", (120, 80), "white"))
    monkeypatch.setattr(imaging, "MAX_PIXELS", 1000)
    with pytest.raises(ValueError, match="megapixel"):
        load_image(source)
    monkeypatch.setattr(imaging, "MAX_PIXELS", 20_000_000)
    with pytest.raises(ValueError):
        load_image(source[:100])


def test_heic_file_path_is_supported(tmp_path):
    path = tmp_path / "phone.HEIC"
    path.write_bytes(heif(Image.new("RGB", (80, 120), "white")))
    assert load_image(path).shape == (120, 80, 3)
