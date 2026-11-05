# ReceiptLens — third-party software and model attribution

This application integrates upstream libraries and pretrained models. Its OCR
detector/recognizers were not trained or fine-tuned by this project.

## Main dependencies

| Component | Use | License information |
|---|---|---|
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | Pretrained OCR pipeline and models | [Apache-2.0](https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE) |
| [PaddlePaddle](https://github.com/PaddlePaddle/Paddle) | CPU inference runtime | Apache-2.0; see upstream distribution notices |
| [OpenCV](https://github.com/opencv/opencv) | Contours, image transforms and thresholding | [Apache-2.0](https://github.com/opencv/opencv/blob/4.x/LICENSE); binary wheels also carry bundled notices |
| [NumPy](https://github.com/numpy/numpy) | Array operations | BSD-3-Clause core; installed wheel includes additional dependency licenses |
| [Pillow](https://github.com/python-pillow/Pillow) | Image loading, sample rendering and image/PDF encoding | [MIT-CMU](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |
| [Streamlit](https://github.com/streamlit/streamlit) | Browser UI and AppTest | Apache-2.0 |
| [pytest](https://github.com/pytest-dev/pytest) | Automated tests | MIT |
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | PDF reopening/render checks in tests | BSD-3-Clause / Apache-2.0 bindings; PDFium and bundled dependencies have separate notices |

This table summarizes main dependencies. `requirements-lock.txt` records the tested
packages, not a complete license inventory. Preserve the license files/notices that
accompany upstream packages and binary distributions.

## Pretrained models

The project explicitly selects these PP-OCRv5 artifacts from PaddleOCR:

- `PP-OCRv5_mobile_det`
- `en_PP-OCRv5_mobile_rec`
- `latin_PP-OCRv5_mobile_rec` (used for Uzbek Latin)
- `korean_PP-OCRv5_mobile_rec`

The downloaded model cards identify Apache-2.0 licensing. Model files remain in
Paddle's cache; they are not copied into this project. The benchmark metadata records
weight checksums for the measured run. See [upstream OCR documentation](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html)
for model interfaces and supported language settings.

## Project-specific code, examples and reference material

The image-processing pipeline, adapters, orchestration, session handling, exports,
evaluation scorer/runner, tests and documentation were implemented for this project
using public library APIs. No source file from a document-scanner repository is bundled.

Classical document-scanning concepts are documented by
[OpenCV's perspective transform tutorial](https://docs.opencv.org/4.x/da/d6e/tutorial_py_geometric_transformations.html).
The CER definition is cross-referenced to
[Hugging Face Evaluate](https://github.com/huggingface/evaluate/blob/main/metrics/cer/cer.py);
the project implements its own tested Levenshtein scorer rather than importing that code.

The English, Uzbek and Korean example texts and synthetic dataset were created for
this project. Sample generation uses locally installed Arial and Apple SD Gothic Neo
fonts. Font binaries are not redistributed; their own vendor licenses remain applicable.
Generated sample images and genuine app screenshots are included as portfolio evidence.

This notice does not assign a license to the project-specific code. No project-wide
open-source license has been selected, and no public release or deployment is implied.

## HEIC input support

[pillow-heif](https://github.com/bigcat88/pillow_heif) provides Pillow HEIC/HEIF decoding (BSD-3-Clause bindings; bundled libheif/codec notices also apply). Original phone images are not copied into repository fixtures.

## Translation and development/deployment tools

- [Requests](https://requests.readthedocs.io/) provides HTTP transport (Apache-2.0).
- [Google Gemini](https://ai.google.dev/gemini-api/terms) is an optional hosted translation service;
  no Gemini weights or proprietary source are distributed. Its service terms apply separately.
- [Ruff](https://github.com/astral-sh/ruff) is the development linter/formatter (MIT).
- [Caddy](https://github.com/caddyserver/caddy) supplies the deployment HTTPS proxy (Apache-2.0).

The project remains named ReceiptLens; the internal `scanner` package describes its original
image-processing domain and is not a separate third-party implementation.
