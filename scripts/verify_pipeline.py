"""Opt-in real-model integration check on synthetic, non-private documents."""

import json
from io import BytesIO
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
from PIL import Image

from scanner.imaging import load_image
from scanner.ocr import create_engine
from scanner.pipeline import process_document
from scanner.scan import save_scan


def main() -> None:
    output = Path("outputs/pipeline")
    output.mkdir(parents=True, exist_ok=True)
    observations = []
    for language in ("en", "uz", "korean"):
        page = load_image(Path("samples") / f"{language}.png")
        height, width = page.shape[:2]
        corners = np.array([[250, 210], [1580, 110], [1650, 1050], [140, 1110]], np.float32)
        matrix = cv2.getPerspectiveTransform(
            np.array(
                [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32
            ),
            corners,
        )
        scene = cv2.warpPerspective(page, matrix, (1800, 1300), borderValue=(65, 75, 85))
        buffer = BytesIO()
        Image.fromarray(scene).save(buffer, "PNG")
        source = buffer.getvalue()
        started = perf_counter()
        engine = create_engine(language)
        initialization_seconds = perf_counter() - started
        entry = {
            "language": language,
            "model_initialization_seconds": round(initialization_seconds, 3),
        }
        for mode, original in (("rectified", False), ("original", True)):
            result = process_document(source, language, use_original=original, engine=engine)
            if not result.ocr.blocks or "12345" not in result.ocr.text:
                raise RuntimeError(
                    f"Expected text and order number not found for {language}/{mode}"
                )
            if not result.scan.detected or result.used_original != original:
                raise RuntimeError(f"Unexpected scan selection for {language}/{mode}")
            payload = result.to_payload()
            target = output / f"{language}-{mode}"
            save_scan(result.scan, target, used_original=result.used_original)
            (target / "result.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            annotated = result.scan.color.copy()
            for block in result.ocr.blocks:
                cv2.polylines(
                    annotated, [np.rint(block.polygon).astype(np.int32)], True, (0, 155, 85), 2
                )
            Image.fromarray(annotated).save(target / "text-blocks.png")
            entry[mode] = {
                "text": result.ocr.text,
                "blocks": len(result.ocr.blocks),
                "scan_seconds": payload["scan_seconds"],
                "inference_seconds": payload["inference_seconds"],
            }
        if language == "en":
            blank = BytesIO()
            Image.new("RGB", (400, 300), "white").save(blank, "PNG")
            empty = process_document(blank.getvalue(), "en", engine=engine)
            if empty.ocr.blocks or not empty.used_original or not empty.warnings:
                raise RuntimeError("Blank-image fallback did not behave as expected")
            entry["blank_image"] = "No text; original retained with boundary warning."
        observations.append(entry)
    (output / "report.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Milestone 3 — scanner and real OCR integration",
        "",
        "All inputs are synthetic perspective scenes generated from the three original sample pages.",
        "Each language uses one cached CPU model instance for both modes. Timings exclude model initialization.",
        "Model initialization is recorded separately in `outputs/pipeline/report.json`.",
        "This check verifies integration; it is not the planned 15-document CER benchmark.",
        "",
        "| Language | Rectified OCR (s) | Original OCR (s) | Rectified blocks |",
        "|---|---:|---:|---:|",
    ]
    for entry in observations:
        lines.append(
            f"| {entry['language']} | {entry['rectified']['inference_seconds']} | {entry['original']['inference_seconds']} | {entry['rectified']['blocks']} |"
        )
    for entry in observations:
        reference = (Path("samples") / f"{entry['language']}.txt").read_text().strip()
        lines.extend(
            ["", f"## {entry['language']}", "", "Reference:", "", "```text", reference, "```"]
        )
        for mode in ("rectified", "original"):
            lines.extend(["", f"Recognized ({mode}):", "", "```text", entry[mode]["text"], "```"])
        if "blank_image" in entry:
            lines.extend(["", "Blank-image check: " + entry["blank_image"]])
    lines.extend(
        [
            "",
            "Text-block overlays and scan previews: `outputs/pipeline/<language>-<mode>/`.",
            "Block polygons refer to the OCR image, not to the uncropped original.",
            "Confidence scores are model scores, not measured accuracy. Original model output is retained.",
            "Run `python -m scripts.verify_pipeline` to repeat this real-model check.",
            "",
        ]
    )
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(observations, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
