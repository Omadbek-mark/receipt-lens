"""Readable receipt lines paired with geometry-based image highlighting."""

import cv2
import numpy as np
import streamlit as st

from scanner.expense_reports import safe_csv_cell
from scanner.i18n import tr
from scanner.layout import aligned_text, reading_rows


def render_ocr_view(result, key: str) -> None:
    rows = reading_rows(result.ocr.blocks)
    left, right = st.columns([1, 1.3])
    selected = []
    with right:
        st.subheader(tr("Receipt text"))
        if rows:
            aligned, line_view = st.tabs([tr("Aligned text"), tr("Select a line")])
            with aligned:
                st.code(aligned_text(result.ocr.blocks), language=None, wrap_lines=False)
                st.caption(
                    tr("Approximate column spacing from the image. Recognition errors may remain.")
                )
            with line_view:
                selection = st.dataframe(
                    [
                        {
                            tr("Line"): index + 1,
                            tr("Text"): safe_csv_cell(" ".join(b.text for b in row)),
                        }
                        for index, row in enumerate(rows)
                    ],
                    hide_index=True,
                    width="stretch",
                    on_select="rerun",
                    selection_mode="single-row",
                    key=key,
                )
                selected = selection.selection.rows
                st.caption(tr("Select a row to highlight that line in the image."))
        else:
            st.warning(
                tr("No text detected. Check the selected language or crop the receipt area.")
            )
    with left:
        image = result.scan.color.copy()
        if selected and selected[0] < len(rows):
            for block in rows[selected[0]]:
                cv2.polylines(
                    image, [np.rint(block.polygon).astype(np.int32)], True, (0, 155, 85), 3
                )
        st.image(image, caption=tr("Image read by OCR"), width="stretch")
        with st.expander(tr("Original image and selected framing")):
            st.image(result.scan.preview, width="stretch")
