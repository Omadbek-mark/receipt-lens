"""Generate three synthetic, non-private smoke-test pages (no external images)."""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TEXTS = {
    "en": "DOCUMENT SCANNER\nThis is a simple English document.\nOrder number: 12345\nTotal: 250 dollars.",
    "uz": "HUJJAT SKANERI\nBu oddiy o‘zbekcha hujjat.\nO‘quv markazi va yangi g‘oyalar.\nBuyurtma raqami: 12345",
    "korean": "문서 스캐너\n이 문서는 한국어 테스트입니다.\n주문 번호: 12345\n감사합니다.",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latin-font", type=Path, required=True)
    parser.add_argument("--korean-font", type=Path, required=True)
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / "samples"
    output.mkdir(exist_ok=True)
    for language, text in TEXTS.items():
        font_path = args.korean_font if language == "korean" else args.latin_font
        font = ImageFont.truetype(str(font_path), size=44)
        image = Image.new("RGB", (1400, 800), "white")
        ImageDraw.Draw(image).multiline_text((90, 110), text, font=font, fill="black", spacing=35)
        image.save(output / f"{language}.png")
        (output / f"{language}.txt").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
