"""Generate a reproducible 15-document synthetic evaluation set, with ground truth."""

import argparse
import json
from hashlib import sha256
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

CONDITIONS = ("clean", "perspective", "shadow", "blur", "shadow_blur")
CORNERS = np.array([[250, 210], [1580, 110], [1650, 1050], [140, 1110]], np.float32)


def make_scene(page: np.ndarray, condition: str) -> tuple[np.ndarray, list | None]:
    if condition not in CONDITIONS:
        raise ValueError("Unknown benchmark condition.")
    if condition == "clean":
        return page.copy(), None
    height, width = page.shape[:2]
    transform = cv2.getPerspectiveTransform(
        np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32),
        CORNERS,
    )
    image = cv2.warpPerspective(page, transform, (1800, 1300), borderValue=(65, 75, 85))
    if "shadow" in condition:
        gradient = np.linspace(0.48, 1.0, image.shape[1])[None, :, None]
        image = (image * gradient).astype(np.uint8)
    if "blur" in condition:
        image = cv2.GaussianBlur(image, (5, 5), 1.2)
    return image, CORNERS.tolist()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latin-font", type=Path, required=True)
    parser.add_argument("--korean-font", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("benchmarks/dataset"))
    args = parser.parse_args()
    texts = json.loads(
        (Path(__file__).resolve().parents[1] / "benchmarks/texts.json").read_text(encoding="utf-8")
    )
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    entries = []
    contact_sheet = Image.new("RGB", (1200, 1550), "#eeeae1")
    for column, language in enumerate(("en", "uz", "korean")):
        font_path = args.korean_font if language == "korean" else args.latin_font
        font = ImageFont.truetype(str(font_path), size=40)
        for index, (condition, text) in enumerate(zip(CONDITIONS, texts[language], strict=True)):
            page = Image.new("RGB", (1400, 1000), "white")
            draw = ImageDraw.Draw(page)
            bounds = draw.multiline_textbbox((90, 100), text, font=font, spacing=30)
            if bounds[2] > 1310 or bounds[3] > 910:
                raise ValueError(f"Text would be clipped in {language}/{condition}.")
            draw.multiline_text((90, 100), text, font=font, fill="black", spacing=30)
            image, corners = make_scene(np.array(page), condition)
            stem = f"{index + 1:02d}-{condition}"
            folder = output / language
            folder.mkdir(exist_ok=True)
            image_path, reference_path = folder / f"{stem}.png", folder / f"{stem}.txt"
            Image.fromarray(image).save(image_path)
            reference_path.write_text(text + "\n", encoding="utf-8")
            entries.append(
                {
                    "id": f"{language}-{stem}",
                    "language": language,
                    "condition": condition,
                    "image": str(image_path.relative_to(output)),
                    "reference": str(reference_path.relative_to(output)),
                    "image_sha256": sha256(image_path.read_bytes()).hexdigest(),
                    "reference_sha256": sha256(reference_path.read_bytes()).hexdigest(),
                    "expected_corners": corners,
                }
            )
            thumbnail = Image.fromarray(image)
            thumbnail.thumbnail((380, 270))
            contact_sheet.paste(thumbnail, (column * 400 + 10, index * 310 + 30))
            ImageDraw.Draw(contact_sheet).text(
                (column * 400 + 10, index * 310 + 10), f"{language}: {condition}", fill="black"
            )
    manifest = {
        "version": 1,
        "origin": "Original synthetic test documents; no real personal data.",
        "generator": {
            "page_size": [1400, 1000],
            "font_size": 40,
            "line_spacing": 30,
            "shadow_gradient": [0.48, 1.0],
            "blur_kernel": [5, 5],
            "blur_sigma": 1.2,
            "latin_font_sha256": sha256(args.latin_font.read_bytes()).hexdigest(),
            "korean_font_sha256": sha256(args.korean_font.read_bytes()).hexdigest(),
        },
        "samples": entries,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    contact_sheet.save(output / "contact-sheet.png")
    print(f"Generated {len(entries)} documents and matching reference texts in {output}.")


if __name__ == "__main__":
    main()
