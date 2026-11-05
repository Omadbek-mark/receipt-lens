"""Document geometry. All public image arrays use RGB uint8, never BGR."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

# Decode iPhone HEIC/HEIF in the existing Pillow path; disable auxiliary thumbnails.
register_heif_opener(thumbnails=False)

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000
DETECTION_SIDE = 1280


@dataclass(frozen=True)
class ScanResult:
    original: np.ndarray
    preview: np.ndarray
    color: np.ndarray
    monochrome: np.ndarray
    corners: tuple[tuple[float, float], ...] | None
    warning: str | None
    crop_box: tuple[int, int, int, int] | None = None
    used_original: bool = False

    @property
    def detected(self) -> bool:
        return self.corners is not None


def load_image(source: bytes | Path) -> np.ndarray:
    """Check limits before decoding pixels, apply EXIF, and composite onto white."""
    if isinstance(source, Path):
        if source.stat().st_size > MAX_BYTES:
            raise ValueError("Image exceeds the 10 MB file limit.")
        data = source.read_bytes()
    else:
        data = source
    if len(data) > MAX_BYTES:
        raise ValueError("Image exceeds the 10 MB file limit.")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in {"JPEG", "PNG", "HEIF"}:
                raise ValueError("Only JPEG, PNG and HEIC/HEIF images are supported.")
            if image.width * image.height > MAX_PIXELS:
                raise ValueError("Image exceeds the 20 megapixel limit.")
            image.load()
            oriented = ImageOps.exif_transpose(image).convert("RGBA")
            background = Image.new("RGBA", oriented.size, "white")
            rgb = Image.alpha_composite(background, oriented).convert("RGB")
            return np.array(rgb)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError(
            "Cannot read this image. Upload a valid JPEG, PNG or HEIC/HEIF."
        ) from error


def order_corners(points: np.ndarray) -> np.ndarray:
    """Return unique convex corners in TL, TR, BR, BL order.

    Angular sorting avoids the duplicated corner problem of independent
    min/max sum and difference selection on diamond-shaped quadrilaterals.
    """
    points = np.asarray(points, dtype=np.float32)
    if points.shape != (4, 2) or not np.isfinite(points).all():
        raise ValueError("Expected four finite corner coordinates.")
    if len(np.unique(points, axis=0)) != 4:
        raise ValueError("Document corners must be distinct.")
    center = points.mean(axis=0)
    angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
    ordered = points[np.argsort(angles)]
    if not cv2.isContourConvex(ordered) or abs(cv2.contourArea(ordered)) < 16:
        raise ValueError("Document corners must form a non-degenerate convex shape.")
    start = int(np.argmin(ordered.sum(axis=1)))
    return np.roll(ordered, -start, axis=0)


def detect_document(rgb: np.ndarray) -> np.ndarray | None:
    height, width = rgb.shape[:2]
    scale = min(1.0, DETECTION_SIDE / max(height, width))
    small = (
        cv2.resize(
            rgb,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
        if scale < 1
        else rgb
    )
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    minimum_area = small.shape[0] * small.shape[1] * 0.15
    for contour in sorted(contours, key=cv2.contourArea, reverse=True):
        if cv2.contourArea(contour) < minimum_area:
            break
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue
        points = order_corners(polygon.reshape(4, 2))
        points *= np.array([width / small.shape[1], height / small.shape[0]], dtype=np.float32)
        if min(np.linalg.norm(np.roll(points, -1, axis=0) - points, axis=1)) < 30:
            continue
        return points
    return None


def rectify(rgb: np.ndarray, corners: np.ndarray) -> np.ndarray:
    top_left, top_right, bottom_right, bottom_left = ordered = order_corners(corners)
    width = round(
        max(np.linalg.norm(top_right - top_left), np.linalg.norm(bottom_right - bottom_left))
    )
    height = round(
        max(np.linalg.norm(bottom_left - top_left), np.linalg.norm(bottom_right - top_right))
    )
    if width < 2 or height < 2 or width * height > MAX_PIXELS:
        raise ValueError("Document dimensions cannot be safely rectified.")
    destination = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32
    )
    transform = cv2.getPerspectiveTransform(ordered, destination)
    return cv2.warpPerspective(rgb, transform, (width, height), borderMode=cv2.BORDER_REPLICATE)


def scan_document(
    rgb: np.ndarray,
    *,
    use_original: bool = False,
    crop_box: tuple[int, int, int, int] | None = None,
) -> ScanResult:
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("Expected an RGB uint8 image.")
    if min(rgb.shape[:2]) < 32 or rgb.shape[0] * rgb.shape[1] > MAX_PIXELS:
        raise ValueError("Image must be at least 32 pixels per side and at most 20 megapixels.")
    working = rgb
    if crop_box is not None:
        if use_original:
            raise ValueError("Choose either original framing or a manual crop.")
        if len(crop_box) != 4 or any(type(value) is not int for value in crop_box):
            raise ValueError("Crop coordinates must be four integer pixels.")
        x0, y0, x1, y1 = crop_box
        if not (
            0 <= x0 < x1 <= rgb.shape[1]
            and 0 <= y0 < y1 <= rgb.shape[0]
            and x1 - x0 >= 32
            and y1 - y0 >= 32
        ):
            raise ValueError("Select a crop inside the image, at least 32 pixels per side.")
        working = rgb[y0:y1, x0:x1]
    corners = None if crop_box else detect_document(working)
    preview = rgb.copy()
    if crop_box:
        x0, y0, x1, y1 = crop_box
        cv2.rectangle(
            preview, (x0, y0), (x1 - 1, y1 - 1), (0, 155, 85), max(2, max(rgb.shape[:2]) // 400)
        )
    if corners is not None:
        cv2.polylines(
            preview,
            [np.rint(corners).astype(np.int32)],
            True,
            (0, 155, 85),
            max(2, round(max(rgb.shape[:2]) / 400)),
            cv2.LINE_AA,
        )
    color = rectify(rgb, corners) if corners is not None and not use_original else working.copy()
    gray = cv2.cvtColor(color, cv2.COLOR_RGB2GRAY)
    monochrome = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 12
    )
    warning = (
        None
        if corners is not None or crop_box
        else "No document boundary found. The original image is retained."
    )
    return ScanResult(
        rgb,
        preview,
        color,
        monochrome,
        None if corners is None else tuple(map(tuple, corners.tolist())),
        warning,
        crop_box,
        crop_box is None and (use_original or corners is None),
    )
