"""Opt-in integration check: downloads models and writes only synthetic outputs.

Run from the project root with its virtual-environment Python.
"""

import json
import platform
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    python = sys.executable
    subprocess.run(
        [
            python,
            "scripts/generate_samples.py",
            "--latin-font",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "--korean-font",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        ],
        cwd=root,
        check=True,
    )
    subprocess.run([python, "-m", "pytest", "-q"], cwd=root, check=True)
    observations = []
    for language in ("en", "uz", "korean"):
        for attempt in (1, 2):
            destination = root / "outputs" / f"{language}-{attempt}.json"
            subprocess.run(
                [
                    python,
                    "-m",
                    "scanner",
                    f"samples/{language}.png",
                    "--lang",
                    language,
                    "--output",
                    str(destination),
                ],
                cwd=root,
                check=True,
            )
            payload = json.loads(destination.read_text(encoding="utf-8"))
            if not payload["text"].strip():
                raise RuntimeError(f"No text detected for {language}")
            observations.append((language, attempt, payload))
    dependencies = subprocess.check_output([python, "-m", "pip", "freeze"], text=True)
    (root / "outputs" / "foundation-requirements.txt").write_text(dependencies, encoding="utf-8")
    report = [
        "# Milestone 1 — real CPU OCR smoke test",
        "",
        f"Environment: Python {platform.python_version()}, {platform.system()} {platform.machine()}.",
        "",
        "Three original clean synthetic pages; two separate process runs per language.",
        "This is an integration check, not a photographic-document accuracy benchmark.",
        "Inspect model initialization logs to confirm cached weights were reused on repeat runs.",
        "",
        "| Language | Run | Initialization (s) | Inference (s) |",
        "|---|---:|---:|---:|",
    ]
    for language, attempt, payload in observations:
        report.append(
            f"| {language} | {attempt} | {payload['initialization_seconds']} | {payload['inference_seconds']} |"
        )
    for language, attempt, payload in observations:
        if attempt != 1:
            continue
        reference = (root / "samples" / f"{language}.txt").read_text(encoding="utf-8").strip()
        report.extend(
            [
                "",
                f"## {language}",
                "",
                "Reference:",
                "",
                "```text",
                reference,
                "```",
                "",
                "Recognized:",
                "",
                "```text",
                payload["text"],
                "```",
            ]
        )
    report.extend(
        [
            "",
            "Raw synthetic outputs are in ignored `outputs/`.",
            "Unit-test results appear in the verification command output.",
            "",
        ]
    )
    (root / "outputs" / "foundation-report.md").write_text("\n".join(report), encoding="utf-8")


if __name__ == "__main__":
    main()
