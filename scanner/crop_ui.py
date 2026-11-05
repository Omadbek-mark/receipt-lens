"""Local manual crop preview; moving handles never initializes OCR."""

from hashlib import sha256

import cv2
import streamlit as st

from scanner.i18n import tr
from scanner.imaging import load_image


def manual_crop(
    data: bytes, prefix: str, disabled: bool
) -> tuple[tuple[int, int, int, int] | None, bool]:
    digest = sha256(data).hexdigest()
    cache_key = f"{prefix}_crop_preview"
    if st.session_state.get(cache_key + "_hash") != digest:
        try:
            st.session_state[cache_key] = load_image(data)
            st.session_state[cache_key + "_hash"] = digest
        except (ValueError, OSError) as error:
            st.error(tr(str(error)))
            return None, False
    image = st.session_state[cache_key]
    st.caption(
        tr(
            "Move the range handles to keep only the receipt. The green box shows the selected area."
        )
    )
    horizontal = st.slider(
        tr("Horizontal crop (%)"),
        0,
        100,
        (0, 100),
        key=f"{prefix}_crop_x_{digest[:12]}",
        disabled=disabled,
    )
    vertical = st.slider(
        tr("Vertical crop (%)"),
        0,
        100,
        (0, 100),
        key=f"{prefix}_crop_y_{digest[:12]}",
        disabled=disabled,
    )
    height, width = image.shape[:2]
    x0, x1 = (round(width * value / 100) for value in horizontal)
    y0, y1 = (round(height * value / 100) for value in vertical)
    valid = x1 - x0 >= 32 and y1 - y0 >= 32
    if not valid:
        st.warning(tr("Keep at least 32 pixels in each direction."))
    preview = image.copy()
    cv2.rectangle(
        preview,
        (x0, y0),
        (max(x0, x1 - 1), max(y0, y1 - 1)),
        (0, 155, 85),
        max(2, max(height, width) // 400),
    )
    st.image(preview, caption=tr("Manual crop preview"), width=480)
    return (x0, y0, x1, y1), valid
