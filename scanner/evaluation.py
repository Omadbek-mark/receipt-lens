"""Character error scoring and paired-result aggregation, without AI imports."""

import unicodedata
from dataclasses import asdict, dataclass


def normalize_text(text: str) -> str:
    """NFC Unicode and collapsed whitespace; preserve case and punctuation.

    Hangul is scored as NFC syllable code points, not decomposed Jamo. Uzbek
    apostrophe variants are deliberately NOT mapped to one another or removed.
    """
    return " ".join(unicodedata.normalize("NFC", text).split())


@dataclass(frozen=True)
class CharacterScore:
    edits: int
    reference_characters: int

    @property
    def cer(self) -> float:
        return self.edits / self.reference_characters

    def to_dict(self) -> dict:
        return asdict(self) | {"cer": self.cer}


def score_text(reference: str, hypothesis: str) -> CharacterScore:
    expected, actual = normalize_text(reference), normalize_text(hypothesis)
    if not expected:
        raise ValueError("CER requires a non-empty normalized reference.")
    # Unit-cost Levenshtein distance, with O(len(hypothesis)) memory.
    previous = list(range(len(actual) + 1))
    for i, char in enumerate(expected, 1):
        row = [i]
        for j, other in enumerate(actual, 1):
            row.append(min(row[-1] + 1, previous[j] + 1, previous[j - 1] + (char != other)))
        previous = row
    return CharacterScore(previous[-1], len(expected))


def summarize(records: list[dict]) -> list[dict]:
    """Micro CER is sum(edits)/sum(reference lengths), never mean(page CER)."""
    if not records:
        raise ValueError("Cannot summarize an empty evaluation.")
    groups = []
    for language in sorted({row["language"] for row in records}):
        for mode in ("original", "auto_scan"):
            selected = [r for r in records if r["language"] == language and r["mode"] == mode]
            if not selected:
                continue
            characters = sum(r["reference_characters"] for r in selected)
            edits = sum(r["edits"] for r in selected)
            groups.append(
                {
                    "language": language,
                    "mode": mode,
                    "documents": len(selected),
                    "edits": edits,
                    "reference_characters": characters,
                    "cer": edits / characters,
                    "mean_ocr_seconds": sum(r["inference_seconds"] for r in selected)
                    / len(selected),
                    "mean_total_seconds": sum(r["total_seconds"] for r in selected) / len(selected),
                    "boundary_detected": sum(r["detected"] for r in selected),
                    "original_retained": sum(r["used_original"] for r in selected),
                }
            )
    return groups
