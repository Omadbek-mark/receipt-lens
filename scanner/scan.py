"""Preview a document scan without loading any AI model."""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

from scanner.imaging import ScanResult, load_image, scan_document

SCAN_FILES = ("boundary.png", "scan-color.png", "scan-bw.png", "scan.json")


def save_scan(result: ScanResult, output_dir: Path, *, used_original: bool) -> None:
    """Persist previews only when the caller explicitly requests files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, array in (
        ("boundary.png", result.preview),
        ("scan-color.png", result.color),
        ("scan-bw.png", result.monochrome),
    ):
        Image.fromarray(array).save(output_dir / filename)
    (output_dir / "scan.json").write_text(
        json.dumps(
            {
                "detected": result.detected,
                "corners": result.corners,
                "used_original": used_original,
                "warning": result.warning,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Find and straighten a document locally.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--original",
        action="store_true",
        help="Keep the original framing if the detected boundary is wrong.",
    )
    args = parser.parse_args()
    targets = [args.output_dir / name for name in SCAN_FILES]
    if args.image.resolve() in [target.resolve() for target in targets]:
        parser.error("Choose another output directory to avoid overwriting the input image.")
    try:
        result = scan_document(load_image(args.image), use_original=args.original)
        save_scan(result, args.output_dir, used_original=args.original or not result.detected)
        print(
            result.warning
            or "Document boundary detected. Inspect boundary.png before using the scan."
        )
        print(f"Saved scan preview to {args.output_dir}")
        return 0
    except (ValueError, OSError) as error:
        print(f"Scan failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
