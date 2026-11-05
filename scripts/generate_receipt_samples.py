"""Three original, synthetic receipt examples with explicit expected fields."""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

EXAMPLES = {
    "en": {
        "text": "DEMO CAFE\nReceipt\nDate: 2026-11-01\nCoffee: 4.00 USD\nSandwich: 6.00 USD\nSubtotal: 10.00 USD\nTax: 1.00 USD\nTOTAL: 11.00 USD\nCash: 20.00 USD\nChange: 9.00 USD\nSynthetic test receipt",
        "merchant": "DEMO CAFE",
        "purchased_on": "2026-11-01",
        "amount": "11.00",
        "currency": "USD",
    },
    "uz": {
        "text": "DEMO KAFE\nChek\nSana: 01.11.2026\nQahva: 50000 UZS\nTaom: 75000 UZS\nJami: 125000 UZS\nNaqd: 150000 UZS\nQaytim: 25000 UZS\nSun’iy sinov cheki",
        "merchant": "DEMO KAFE",
        "purchased_on": "2026-11-01",
        "amount": "125000.00",
        "currency": "UZS",
    },
    "korean": {
        "text": "데모 카페\n영수증\n날짜: 2026-11-01\n커피: 5000원\n샌드위치: 7000원\n합계: 12000원\n받은 금액: 15000원\n거스름돈: 3000원\n가상 테스트 영수증",
        "merchant": "데모 카페",
        "purchased_on": "2026-11-01",
        "amount": "12000",
        "currency": "KRW",
    },
}


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "samples/receipts"
    output.mkdir(parents=True, exist_ok=True)
    for language, example in EXAMPLES.items():
        font_path = (
            "/System/Library/Fonts/AppleSDGothicNeo.ttc"
            if language == "korean"
            else "/System/Library/Fonts/Supplemental/Arial.ttf"
        )
        font = ImageFont.truetype(font_path, 38)
        image = Image.new("RGB", (1000, 1200), "white")
        ImageDraw.Draw(image).multiline_text(
            (75, 85), example["text"], font=font, fill="black", spacing=28
        )
        image.save(output / f"{language}.png")
        (output / f"{language}.txt").write_text(example["text"] + "\n", encoding="utf-8")
    (output / "expected.json").write_text(
        json.dumps(EXAMPLES, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
