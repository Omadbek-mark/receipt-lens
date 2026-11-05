"""Run with: python -m scanner samples/en.png --lang en"""

import argparse
import json
import sys
from pathlib import Path

from scanner.ocr import LANGUAGES
from scanner.pipeline import ProcessingError, process_document
from scanner.scan import SCAN_FILES, save_scan


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="receipt-lens",
        description="ReceiptLens: straighten and read a document locally with PP-OCRv5.",
    )
    parser.add_argument("image", type=Path)
    parser.add_argument("--lang", choices=LANGUAGES, required=True)
    parser.add_argument(
        "--output", type=Path, help="Optional JSON result; only use for non-private samples."
    )
    parser.add_argument(
        "--original",
        action="store_true",
        help="Read the original image if the detected boundary is wrong.",
    )
    parser.add_argument(
        "--scan-output-dir", type=Path, help="Optional directory for scan previews."
    )
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error("Input image does not exist.")
    scan_targets = (
        [args.scan_output_dir / name for name in SCAN_FILES] if args.scan_output_dir else []
    )
    outputs = ([args.output] if args.output else []) + scan_targets
    if args.image.resolve() in [target.resolve() for target in outputs]:
        parser.error("Output files must not overwrite the input image.")
    if args.output and args.output.resolve() in [target.resolve() for target in scan_targets]:
        parser.error("JSON output must have a different path from scan preview files.")
    try:
        result = process_document(
            args.image,
            args.lang,
            use_original=args.original,
            on_progress=lambda message: print(f"{message}...", file=sys.stderr),
        )
        payload = result.to_payload()
        if args.scan_output_dir:
            save_scan(result.scan, args.scan_output_dir, used_original=result.used_original)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        for warning in result.warnings:
            print(f"Warning: {warning}", file=sys.stderr)
        print(
            result.ocr.text
            or "No text detected. Try a clearer image or check the selected language."
        )
        print(f"\nInference: {payload['inference_seconds']}s; confidence scores are not accuracy.")
        return 0
    except (ProcessingError, ValueError, OSError) as error:
        print(f"Processing failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
