"""Explicit paid/quota-consuming provider smoke check, using synthetic text only."""

import argparse
import os
import tomllib
from pathlib import Path

from scanner.translation import TranslationError, translate_lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--send-demo", action="store_true", help="Send three non-private demo requests to Gemini."
    )
    args = parser.parse_args()
    if not args.send_demo:
        parser.error("Use --send-demo only when ready to send the three synthetic requests.")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        secret = Path(__file__).resolve().parents[1] / ".streamlit/secrets.toml"
        if secret.exists():
            with secret.open("rb") as stream:
                key = tomllib.load(stream).get("gemini", {}).get("api_key", "").strip()
    if not key:
        parser.exit(1, "Configure the server Gemini key first. Do not paste it into chat.\n")
    cases = [
        ("korean", "en", ["가상 카페", "합계 12,000 KRW"]),
        ("en", "uz", ["Demo cafe", "Total 12.00 USD"]),
        ("uz", "korean", ["Namunaviy kafe", "Jami 12000 UZS"]),
    ]
    try:
        for source, target, lines in cases:
            result = translate_lines(lines, source, target, key)
            print(f"{source} -> {target}: {len(result)} lines returned; numeric checks passed.")
    except TranslationError as error:
        parser.exit(1, str(error) + "\n")
    print("Provider connectivity/structure passed. Translation meaning still needs human review.")


if __name__ == "__main__":
    main()
