from io import BytesIO
from itertools import permutations

import cv2
import numpy as np
import pytest
from PIL import Image

from scanner import imaging
from scanner.imaging import load_image, order_corners, rectify, scan_document


def encoded(image, fmt="PNG", **kwargs):
    buffer = BytesIO()
    image.save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


def page_scene():
    rgb = np.full((700, 900, 3), (60, 70, 80), dtype=np.uint8)
    corners = np.array([[180, 90], [700, 145], [760, 600], [110, 570]], dtype=np.int32)
    cv2.fillConvexPoly(rgb, corners, (245, 245, 245))
    cv2.putText(rgb, "DOCUMENT", (220, 260), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (10, 10, 10), 3)
    return rgb, corners


def test_detects_quadrilateral_and_rectifies_with_correct_coordinates():
    rgb, expected = page_scene()
    result = scan_document(rgb)
    assert result.detected and result.warning is None
    assert np.max(np.linalg.norm(np.asarray(result.corners) - expected, axis=1)) < 6
    assert result.color.shape[0] < rgb.shape[0]
    assert result.color.shape[1] < rgb.shape[1]
    assert result.color[20, 20].mean() > 230
    assert set(np.unique(result.monochrome)) <= {0, 255}
    assert np.array_equal(result.original, rgb)
    assert not np.array_equal(result.preview, rgb)


def test_original_override_preserves_full_image_even_when_document_found():
    rgb, _ = page_scene()
    result = scan_document(rgb, use_original=True)
    assert result.detected
    assert np.array_equal(result.color, rgb)


def test_blank_image_retains_original_and_warns():
    rgb = np.full((200, 300, 3), 255, dtype=np.uint8)
    result = scan_document(rgb)
    assert not result.detected and result.warning
    assert np.array_equal(result.color, rgb)


def test_detection_resize_maps_corners_back_to_original():
    rgb, expected = page_scene()
    large = cv2.resize(rgb, (1800, 1400))
    result = scan_document(large)
    assert result.detected
    assert np.max(np.linalg.norm(np.asarray(result.corners) - expected * 2, axis=1)) < 12


def test_all_corner_permutations_produce_same_order_including_diamond():
    for points in (
        [[10, 10], [110, 10], [110, 210], [10, 210]],
        [[100, 0], [200, 100], [100, 200], [0, 100]],
    ):
        expected = order_corners(np.array(points))
        for permutation in permutations(points):
            assert np.array_equal(order_corners(np.array(permutation)), expected)
        assert len(np.unique(expected, axis=0)) == 4


@pytest.mark.parametrize(
    "points",
    [
        [[0, 0]] * 4,
        [[0, 0], [1, 1], [2, 2], [3, 3]],
        [[0, 0], [100, 0], [20, 20], [0, 100]],
        [[0, 0], [100, 0], [100, float("nan")], [0, 100]],
    ],
)
def test_invalid_geometry_is_rejected(points):
    with pytest.raises(ValueError):
        order_corners(np.array(points))


def test_rectification_preserves_rgb_corner_positions():
    image = np.full((200, 300, 3), 255, np.uint8)
    image[30:60, 30:60] = (255, 0, 0)
    image[140:170, 240:270] = (0, 0, 255)
    result = rectify(image, np.array([[20, 20], [280, 20], [280, 180], [20, 180]]))
    assert result[20, 20].tolist() == [255, 0, 0]
    assert result[-20, -20].tolist() == [0, 0, 255]


def test_exif_orientation_is_applied():
    image = Image.new("RGB", (80, 40), "white")
    exif = image.getexif()
    exif[274] = 6
    assert load_image(encoded(image, "JPEG", exif=exif)).shape == (80, 40, 3)


def test_transparency_is_composited_on_white():
    image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    assert np.all(load_image(encoded(image)) == 255)


def test_invalid_and_unsupported_files_are_rejected():
    for data in (b"not an image", encoded(Image.new("RGB", (40, 40)), "GIF")):
        with pytest.raises(ValueError):
            load_image(data)


def test_size_limits_are_enforced_before_pixel_decode(monkeypatch):
    data = encoded(Image.new("RGB", (40, 40)))
    monkeypatch.setattr(imaging, "MAX_BYTES", len(data) - 1)
    with pytest.raises(ValueError, match="10 MB"):
        load_image(data)
    monkeypatch.setattr(imaging, "MAX_BYTES", len(data) + 1)
    monkeypatch.setattr(imaging, "MAX_PIXELS", 1000)
    with pytest.raises(ValueError, match="megapixel"):
        load_image(data)


@pytest.mark.parametrize(
    "image",
    [
        np.zeros((10, 10, 3), np.uint8),
        np.zeros((100, 100), np.uint8),
        np.zeros((100, 100, 3), np.float32),
    ],
)
def test_invalid_arrays_are_rejected(image):
    with pytest.raises(ValueError):
        scan_document(image)
