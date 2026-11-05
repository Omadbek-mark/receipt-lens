"""Real OCR + field scoring + temporary-account ledger check on synthetic receipts."""

import json
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from scanner.expense_store import DuplicateReceipt, ExpenseStore
from scanner.ocr import create_engine
from scanner.pipeline import process_document
from scanner.receipts import extract_receipt


def main():
    root = Path(__file__).resolve().parents[1]
    expected = json.loads((root / "samples/receipts/expected.json").read_text())
    output = root / "outputs/receipts"
    output.mkdir(parents=True, exist_ok=True)
    observations = []
    with TemporaryDirectory(prefix="receipt-ledger-test-") as directory:
        store = ExpenseStore(Path(directory) / "isolated.sqlite3")
        owner = store.register("synthetic_owner", "synthetic-smoke-password-123")
        other = store.register("synthetic_other", "synthetic-other-password-123")
        for language in ("en", "uz", "korean"):
            source = (root / "samples/receipts" / f"{language}.png").read_bytes()
            result = process_document(source, language, engine=create_engine(language))
            proposal = extract_receipt(result.ocr.text)
            matches = {
                field: getattr(proposal, field) == expected[language][field]
                for field in ("merchant", "purchased_on", "amount", "currency")
            }
            observations.append(
                {
                    "language": language,
                    "proposal": asdict(proposal),
                    "expected": expected[language],
                    "field_matches": matches,
                    "ocr_text": result.ocr.text,
                    "inference_seconds": result.inference_seconds,
                }
            )
            # Simulate the mandatory human review with known synthetic truth. This
            # is NOT an assertion that unreviewed model proposals were all correct.
            reviewed = {
                field: expected[language][field]
                for field in ("merchant", "purchased_on", "amount", "currency")
            }
            buffer = BytesIO()
            Image.fromarray(result.scan.original).save(buffer, "JPEG")
            fields = dict(
                **reviewed,
                category="Food",
                note="Synthetic reviewed test only",
                source=source,
                image=buffer.getvalue(),
                ocr_text=result.ocr.text,
            )
            identifier = store.save(owner, **fields)
            assert store.get(owner, identifier) is not None
            assert store.get(other, identifier) is None
            try:
                store.save(owner, **fields)
                raise AssertionError("Duplicate image was saved twice")
            except DuplicateReceipt:
                pass
            print(
                f"{language}: {sum(matches.values())}/4 exact proposed fields; reviewed save and owner isolation passed",
                flush=True,
            )
        assert len(store.list(owner, "2026-01-01", "2026-12-31")) == 3
        assert store.list(other, "2026-01-01", "2026-12-31") == []
    (output / "real-model-fields.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Receipt and personal-expense verification",
        "",
        "Three original, clean synthetic receipt images were read with the real cached CPU OCR models.",
        "Field extraction uses conservative rules; it is not an LLM or a separately trained extraction model.",
        "The following scores compare unedited proposals with the explicit reference fields.",
        "",
        "| Language | Merchant | Date | Amount | Currency | Exact fields |",
        "|---|---|---|---|---|---:|",
    ]
    for row in observations:
        matches = row["field_matches"]
        flags = [
            "yes" if matches[field] else "no"
            for field in ("merchant", "purchased_on", "amount", "currency")
        ]
        lines.append(f"| {row['language']} | {' | '.join(flags)} | {sum(matches.values())}/4 |")
    lines.extend(
        [
            "",
            "The ledger checks used known reference values to simulate user corrections and confirmation.",
            "All three reviewed records saved, exact-image duplicates were rejected, and a second account",
            "could not list or retrieve the first account's receipts. The test database was temporary;",
            "no operational account or personal receipt database was seeded.",
            "",
            "This tiny clean set is an integration check, not receipt-field accuracy on real merchants/camera photos.",
            "Raw OCR text/proposals: `outputs/receipts/real-model-fields.json` (ignored QA output).",
            "Reference text/fields: `samples/receipts/expected.json`.",
            "",
        ]
    )
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
