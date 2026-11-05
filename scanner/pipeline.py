"""Validated document → color scan → CPU OCR, without temporary image files."""

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import BoundedSemaphore
from time import perf_counter
from typing import Any, Callable

from scanner.imaging import ScanResult, load_image, scan_document
from scanner.ocr import LANGUAGES, OCRResult, create_engine, recognize

PROCESSOR = BoundedSemaphore(1)


@contextmanager
def processor_slot(notify):
    acquired = PROCESSOR.acquire(blocking=False)
    if not acquired:
        notify("Waiting for the document processor")
        acquired = PROCESSOR.acquire(timeout=30)
    if not acquired:
        raise ProcessingError("busy", "The document processor is busy. Please retry shortly.")
    try:
        yield
    finally:
        PROCESSOR.release()


class ProcessingError(RuntimeError):
    """Safe error message for a failed model stage; no input content is exposed."""

    def __init__(self, stage: str, message: str):
        self.stage = stage
        super().__init__(message)


@dataclass(frozen=True)
class ProcessedDocument:
    scan: ScanResult
    ocr: OCRResult
    used_original: bool
    scan_seconds: float
    initialization_seconds: float
    inference_seconds: float

    @property
    def warnings(self) -> tuple[str, ...]:
        return (self.scan.warning,) if self.scan.warning else ()

    def to_payload(self) -> dict[str, Any]:
        """JSON-ready metadata. Image arrays stay in memory for the future UI."""
        return asdict(self.ocr) | {
            "text": self.ocr.text,
            "warnings": list(self.warnings),
            "scan": {
                "detected": self.scan.detected,
                "corners": self.scan.corners,
                "corner_coordinate_space": "exif_oriented_original",
                "used_original": self.used_original,
                "crop_box": self.scan.crop_box,
            },
            "ocr_image": {
                "width": self.scan.color.shape[1],
                "height": self.scan.color.shape[0],
                "mode": "RGB",
                "block_coordinate_space": "ocr_image",
            },
            "scan_seconds": round(self.scan_seconds, 3),
            "initialization_seconds": round(self.initialization_seconds, 3),
            "inference_seconds": round(self.inference_seconds, 3),
        }


def process_document(
    source: bytes | Path,
    language: str,
    *,
    use_original: bool = False,
    crop_box: tuple[int, int, int, int] | None = None,
    engine: Any = None,
    engine_loader: Callable[[str], Any] | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> ProcessedDocument:
    """Reuse a language-matched engine when supplied (e.g. a UI resource cache).

    Bad input raises ValueError/OSError before model initialization. Model startup
    and inference failures have distinct ProcessingError.stage values. There is
    no silent OCR retry or hidden image write. Engine ownership stays with caller.
    """
    if language not in LANGUAGES:
        raise ValueError("Choose Uzbek (Latin), Korean or English.")
    notify = on_progress or (lambda message: None)
    notify("Preparing document")
    started = perf_counter()
    scan = scan_document(load_image(source), use_original=use_original, crop_box=crop_box)
    scanned = perf_counter()
    with processor_slot(notify):
        if engine is None:
            notify("Loading OCR model")
            try:
                engine = (engine_loader or create_engine)(language)
            except Exception as error:
                raise ProcessingError(
                    "model_loading",
                    "Could not load the OCR model. Check the installation and model download connection.",
                ) from error
        initialized = perf_counter()
        notify("Reading document text")
        try:
            result = recognize(engine, scan.color, language)
        except Exception as error:
            raise ProcessingError(
                "recognition",
                "Could not read the document. Try a clearer image or retry processing.",
            ) from error
    finished = perf_counter()
    return ProcessedDocument(
        scan,
        result,
        scan.used_original,
        scanned - started,
        initialized - scanned,
        finished - initialized,
    )
