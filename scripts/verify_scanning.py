"""Generate reproducible perspective scenes and inspect document geometry.

Uses only an existing synthetic sample; never reads private document directories.
"""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from scanner.imaging import load_image, scan_document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=Path, default=Path("samples/en.png"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/scanning"))
    args = parser.parse_args()
    page = load_image(args.sample)
    height, width = page.shape[:2]
    expected = np.array([[250, 210], [1580, 110], [1650, 1050], [140, 1110]], np.float32)
    transform = cv2.getPerspectiveTransform(
        np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32),
        expected,
    )
    scene = cv2.warpPerspective(page, transform, (1800, 1300), borderValue=(65, 75, 85))
    gradient = np.linspace(0.65, 1.0, scene.shape[1])[None, :, None]
    shadowed = cv2.GaussianBlur((scene * gradient).astype(np.uint8), (3, 3), 0)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    observations = []
    for name, image in (("perspective", scene), ("shadow-blur", shadowed)):
        result = scan_document(image)
        error = (
            None
            if result.corners is None
            else float(np.max(np.linalg.norm(np.asarray(result.corners) - expected, axis=1)))
        )
        observations.append(
            {
                "scene": name,
                "detected": result.detected,
                "max_corner_error_pixels": error,
                "output_size": [result.color.shape[1], result.color.shape[0]],
            }
        )
        for suffix, array in (
            ("source", image),
            ("boundary", result.preview),
            ("color", result.color),
            ("bw", result.monochrome),
        ):
            Image.fromarray(array).save(args.output_dir / f"{name}-{suffix}.png")
        comparison = Image.new("RGB", (1500, 460), "#eeeae1")
        draw = ImageDraw.Draw(comparison)
        for index, (title, array) in enumerate(
            (
                ("Detected boundary", result.preview),
                ("Rectified color", result.color),
                ("Black and white", result.monochrome),
            )
        ):
            thumbnail = Image.fromarray(array).convert("RGB")
            thumbnail.thumbnail((480, 400))
            comparison.paste(thumbnail, (index * 500 + 10, 45))
            draw.text((index * 500 + 10, 15), title, fill="black")
        comparison.save(args.output_dir / f"{name}-comparison.png")
    (args.output_dir / "report.json").write_text(
        json.dumps(observations, indent=2), encoding="utf-8"
    )
    print(json.dumps(observations, indent=2))
    if any(not item["detected"] or item["max_corner_error_pixels"] > 15 for item in observations):
        raise SystemExit("Geometry verification failed; inspect the saved previews.")


if __name__ == "__main__":
    main()
