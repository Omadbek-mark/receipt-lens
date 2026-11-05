"""Run paired original/auto-scan OCR and produce reproducible CER evidence."""

import argparse
import csv
import json
import platform
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

import numpy as np

from scanner.evaluation import normalize_text, score_text, summarize
from scanner.imaging import load_image
from scanner.ocr import LANGUAGES, RECOGNIZERS, create_engine
from scanner.pipeline import process_document


def load_samples(manifest_path: Path) -> tuple[dict, list[dict]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != 1 or not manifest.get("samples"):
        raise ValueError("Expected a version 1 manifest with samples.")
    root = manifest_path.parent.resolve()
    ids, samples = set(), []
    for entry in manifest["samples"]:
        identifier = entry["id"]
        if identifier in ids or entry["language"] not in LANGUAGES:
            raise ValueError("Sample IDs must be unique and languages supported.")
        ids.add(identifier)
        paths = {}
        for field in ("image", "reference"):
            path = (root / entry[field]).resolve()
            if not path.is_relative_to(root):
                raise ValueError("Sample paths must stay inside the dataset directory.")
            data = path.read_bytes()
            if sha256(data).hexdigest() != entry[f"{field}_sha256"]:
                raise ValueError(f"Dataset checksum mismatch for {identifier}/{field}.")
            paths[field] = path
        reference = paths["reference"].read_text(encoding="utf-8")
        if not normalize_text(reference):
            raise ValueError("Reference texts must not be empty.")
        # Reject corrupt or oversized images before initializing any AI model.
        load_image(paths["image"])
        expected = entry.get("expected_corners")
        if expected is not None and (
            np.asarray(expected).shape != (4, 2)
            or not np.isfinite(np.asarray(expected, dtype=float)).all()
        ):
            raise ValueError("Expected corners must be four finite coordinate pairs.")
        samples.append(entry | {"image_path": paths["image"], "reference_text": reference})
    return manifest, samples


def write_report(
    records: list[dict], metadata: dict, report_path: Path, result_folder: Path
) -> None:
    summary = summarize(records)
    lines = [
        "# Milestone 5 — multilingual OCR evaluation",
        "",
        "This is a small synthetic development evaluation, not a held-out real-world accuracy claim.",
        f"Run UTC: {metadata['run_utc']}. Python {metadata['python']}; {metadata['system']} {metadata['architecture']} CPU.",
        f"Dataset: {metadata['document_count']} distinct documents, five per language; each evaluated in two paired modes.",
        "",
        "## Method",
        "",
        "CER = Levenshtein character edits / reference character count. Lower is better; CER can exceed 100%.",
        "NFC Unicode normalization and whitespace collapse are applied to both strings. Case, punctuation,",
        "spaces between words and apostrophe variants remain significant. Korean is scored by NFC syllable",
        "code points. Raw reference and recognized strings are retained in the result JSON.",
        "Micro CER aggregates edits and reference lengths, rather than averaging page percentages.",
        "Definition reference: [Hugging Face Evaluate CER](https://github.com/huggingface/evaluate/blob/main/metrics/cer/cer.py).",
        "",
        "One CPU model is reused per language after one warm-up inference. Model initialization and warm-up",
        "are excluded from reported per-document times and recorded separately. Each pair is measured once;",
        "the first mode alternates between samples to reduce systematic order bias. Timings are indicative.",
        "Original mode retains full framing. Auto-scan attempts perspective correction and retains the original",
        "when no border is found. Both modes use the same pipeline, including input validation and border detection.",
        "",
        "## Per-language results",
        "",
        "| Language | Mode | Documents | Edits / characters | Micro CER | Mean OCR (s) | Mean total (s) | Original retained |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"| {row['language']} | {row['mode']} | {row['documents']} | {row['edits']} / {row['reference_characters']} | {row['cer']:.2%} | {row['mean_ocr_seconds']:.3f} | {row['mean_total_seconds']:.3f} | {row['original_retained']} |"
        )
    lines += [
        "",
        "## Per-document paired results",
        "",
        "| Document | Original CER | Auto-scan CER | Auto-scan OCR (s) | Border found | Maximum corner error (px) |",
        "|---|---:|---:|---:|---|---:|",
    ]
    for sample_id in dict.fromkeys(row["id"] for row in records):
        pair = {r["mode"]: r for r in records if r["id"] == sample_id}
        original, auto = pair["original"], pair["auto_scan"]
        error = auto["max_corner_error_pixels"]
        error_label = "n/a" if error is None else f"{error:.2f}"
        lines.append(
            f"| {sample_id} | {original['cer']:.2%} | {auto['cer']:.2%} | {auto['inference_seconds']:.3f} | {auto['detected']} | {error_label} |"
        )
    lines += [
        "",
        "## Limits and interpretation",
        "",
        "- The 15 texts are original synthetic documents, rendered with one font family per script.",
        "- There are five different texts per language, one per condition. Cross-condition scores are confounded",
        "  by document content; only original versus auto-scan on the same input is a paired comparison.",
        "- Clean images fill the frame and have no surrounding border; original retention is expected.",
        "- The remaining images have known four-corner perspective geometry. Shadow is a 0.48–1.0 brightness",
        "  gradient; mild blur is a 5×5 Gaussian filter with sigma 1.2. Generator details are in the manifest.",
        "- Synthetic rendering does not model real camera focus, glare, folds, lens distortion or difficult layouts.",
        "- No model training, text correction or parameter tuning was performed during this evaluation.",
        "- A low CER on these few pages must not be advertised as general language recognition accuracy.",
        "- Empty OCR output is scored as full reference deletion; processing errors stop the run and leave",
        "  a partial progress file. A complete report is written only after all pairs succeed.",
        "",
        "## Evidence",
        "",
        f"Raw strings, scores, warnings and coordinates: `{result_folder}/results.json`.",
        f"Per-document table: `{result_folder}/results.csv`.",
        f"Environment, dataset and model checksums: `{result_folder}/metadata.json`.",
        "Source images and references: `benchmarks/dataset/`; overview: `benchmarks/dataset/contact-sheet.png`.",
        "",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def run(manifest_path: Path, output_root: Path, report_path: Path) -> Path:
    _, samples = load_samples(manifest_path)
    stamp = datetime.now(timezone.utc)
    output = output_root / stamp.strftime("run-%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=False)
    metadata = {
        "run_utc": stamp.isoformat(),
        "python": platform.python_version(),
        "system": platform.system(),
        "architecture": platform.machine(),
        "device": "cpu",
        "document_count": len(samples),
        "manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
        "packages": {
            name: version(name)
            for name in ("paddleocr", "paddlepaddle", "numpy", "opencv-contrib-python", "Pillow")
        },
        "normalization": "NFC; collapse whitespace; retain case, punctuation and apostrophe variants",
        "model_initialization_seconds": {},
        "warmup_seconds": {},
        "weight_checksums": {},
        "protocol": "One warm-up per language, one run per mode/sample; alternating mode order.",
    }
    records = []
    progress_path = output / "progress.json"
    progress_path.write_text(json.dumps({"complete": False, "records": []}), encoding="utf-8")
    for language in dict.fromkeys(sample["language"] for sample in samples):
        language_samples = [s for s in samples if s["language"] == language]
        started = perf_counter()
        engine = create_engine(language)
        metadata["model_initialization_seconds"][language] = perf_counter() - started
        started = perf_counter()
        process_document(
            language_samples[0]["image_path"], language, engine=engine, use_original=True
        )
        metadata["warmup_seconds"][language] = perf_counter() - started
        for index, sample in enumerate(language_samples):
            modes = ("original", "auto_scan") if index % 2 == 0 else ("auto_scan", "original")
            for mode in modes:
                started = perf_counter()
                result = process_document(
                    sample["image_path"], language, engine=engine, use_original=mode == "original"
                )
                total_seconds = perf_counter() - started
                score = score_text(sample["reference_text"], result.ocr.text)
                error = None
                if sample.get("expected_corners") is not None and result.scan.corners is not None:
                    error = float(
                        np.max(
                            np.linalg.norm(
                                np.asarray(result.scan.corners) - sample["expected_corners"], axis=1
                            )
                        )
                    )
                record = {
                    "id": sample["id"],
                    "language": language,
                    "condition": sample["condition"],
                    "mode": mode,
                    "reference": sample["reference_text"],
                    "hypothesis": result.ocr.text,
                    **score.to_dict(),
                    "detected": result.scan.detected,
                    "used_original": result.used_original,
                    "max_corner_error_pixels": error,
                    "total_seconds": total_seconds,
                    "inference_seconds": result.inference_seconds,
                    "scan_seconds": result.scan_seconds,
                    "payload": result.to_payload(),
                }
                records.append(record)
            progress_path.write_text(
                json.dumps({"complete": False, "records": records}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(
                f"Completed {sample['id']} ({len(records)}/{2 * len(samples)} measurements)",
                flush=True,
            )
        del engine
    for model in ("PP-OCRv5_mobile_det", *RECOGNIZERS.values()):
        folder = Path.home() / ".paddlex/official_models" / model
        metadata["weight_checksums"][model] = {
            file.name: sha256(file.read_bytes()).hexdigest()
            for file in sorted(folder.glob("*.pdiparams"))
        }
    summary = summarize(records)
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (output / "results.json").write_text(
        json.dumps(
            {"complete": True, "summary": summary, "records": records}, ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )
    fields = [
        "id",
        "language",
        "condition",
        "mode",
        "edits",
        "reference_characters",
        "cer",
        "detected",
        "used_original",
        "max_corner_error_pixels",
        "inference_seconds",
        "scan_seconds",
        "total_seconds",
    ]
    with (output / "results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row[field] for field in fields} for row in records)
    progress_path.write_text(
        json.dumps({"complete": True, "measurements": len(records)}), encoding="utf-8"
    )
    write_report(records, metadata, report_path, output)
    print(json.dumps(summary, indent=2), flush=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("benchmarks/dataset/manifest.json"))
    parser.add_argument("--output-root", type=Path, default=Path("outputs/benchmarks"))
    parser.add_argument("--report", type=Path, default=Path("outputs/benchmark-report.md"))
    args = parser.parse_args()
    run(args.manifest, args.output_root, args.report)


if __name__ == "__main__":
    main()
