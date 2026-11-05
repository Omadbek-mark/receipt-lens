"""Geometry-based text lines and an approximate, Unicode-aware column layout."""

from __future__ import annotations

import unicodedata
from math import atan2, cos, sin
from statistics import median
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from scanner.ocr import TextBlock


def _angle(blocks):
    slopes = []
    for block in blocks:
        a, b = block.polygon[:2]
        dx, dy = b[0] - a[0], b[1] - a[1]
        if dx > 0:
            angle = atan2(dy, dx)
            if abs(angle) <= 0.44:  # grouping deskews modest text tilt, not vertical writing
                slopes.append(angle)
    return median(slopes) if slopes else 0.0


def _geometry(block, angle):
    c, s = cos(angle), sin(angle)
    points = [(x * c + y * s, -x * s + y * c) for x, y in block.polygon]
    xs, ys = zip(*points)
    return min(xs), max(xs), (min(ys) + max(ys)) / 2, max(ys) - min(ys)


def reading_rows(blocks: Iterable[TextBlock]) -> list[list[TextBlock]]:
    blocks = list(blocks)
    if not blocks:
        return []
    angle = _angle(blocks)
    geometry = {id(block): _geometry(block, angle) for block in blocks}
    rows = []
    for block in sorted(blocks, key=lambda b: geometry[id(b)][2]):
        _, _, center, height = geometry[id(block)]
        candidate, distance = None, float("inf")
        for row in rows[-3:]:
            row_center = median(geometry[id(b)][2] for b in row)
            row_height = median(geometry[id(b)][3] for b in row)
            delta = abs(center - row_center)
            if delta <= 0.55 * min(height, row_height) and delta < distance:
                candidate, distance = row, delta
        if candidate is None:
            rows.append([block])
        else:
            candidate.append(block)
    rows.sort(key=lambda row: median(geometry[id(b)][2] for b in row))
    return [sorted(row, key=lambda b: geometry[id(b)][0]) for row in rows]


def display_width(text: str) -> int:
    return sum(
        0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in {"W", "F"} else 1
        for c in text
    )


def aligned_text(blocks: Iterable[TextBlock]) -> str:
    blocks = list(blocks)
    if not blocks:
        return ""
    angle = _angle(blocks)
    geometry = {id(block): _geometry(block, angle) for block in blocks}
    left = min(g[0] for g in geometry.values())
    right = max(g[1] for g in geometry.values())
    widths = [
        (geometry[id(b)][1] - geometry[id(b)][0]) / max(1, display_width(b.text)) for b in blocks
    ]
    unit = max(1.0, median(widths), (right - left) / 180)
    lines = []
    for row in reading_rows(blocks):
        line, used = "", 0
        for block in row:
            column = round((geometry[id(block)][0] - left) / unit)
            spaces = max(1 if line else 0, column - used)
            line += " " * spaces + block.text
            used += spaces + display_width(block.text)
        lines.append(line.rstrip())
    return "\n".join(lines)
