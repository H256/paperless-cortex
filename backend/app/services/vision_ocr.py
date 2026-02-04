from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import logging

from app.config import Settings
from app.services import ollama
from app.services.page_types import PageText

logger = logging.getLogger(__name__)

DEFAULT_VISION_PROMPT = "Extract all readable text from this page image. Return only the text."

_prompt_cache: dict[str, str] = {}


def load_prompt(settings: Settings) -> str:
    if settings.vision_ocr_prompt:
        return settings.vision_ocr_prompt
    path = settings.vision_ocr_prompt_path
    if not path:
        return DEFAULT_VISION_PROMPT
    if path in _prompt_cache:
        return _prompt_cache[path]
    prompt_path = Path(path)
    if not prompt_path.is_file():
        logger.warning("Vision OCR prompt file not found path=%s", path)
        return DEFAULT_VISION_PROMPT
    text = prompt_path.read_text(encoding="utf-8").strip()
    if not text:
        logger.warning("Vision OCR prompt file empty path=%s", path)
        return DEFAULT_VISION_PROMPT
    _prompt_cache[path] = text
    logger.info("Loaded vision OCR prompt from file path=%s", path)
    return text


@dataclass(frozen=True)
class VisionPage:
    page_index: int
    image_bytes: bytes



def _render_page_image(doc: "fitz.Document", page_index: int, max_dim: int) -> bytes:
    try:
        import fitz  # PyMuPDF
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("pymupdf is required for vision OCR") from exc
    page = doc.load_page(page_index)
    rect = page.rect
    width = float(rect.width)
    height = float(rect.height)
    if max_dim <= 0:
        scale = 1.0
    else:
        scale = min(max_dim / max(width, 1.0), max_dim / max(height, 1.0))
        if scale > 1.0:
            scale = 1.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    return pix.tobytes("png")


def render_pdf_pages(pdf_bytes: bytes, page_numbers: Iterable[int] | None, max_dim: int) -> list[VisionPage]:
    try:
        import fitz  # PyMuPDF
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("pymupdf is required for vision OCR") from exc

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if page_numbers is None:
        page_indices = list(range(len(doc)))
    else:
        page_indices = [max(0, p - 1) for p in page_numbers]
    logger.info("Rendering PDF pages for vision OCR pages=%s", [p + 1 for p in page_indices])
    rendered: list[VisionPage] = []
    for page_index in page_indices:
        png_bytes = _render_page_image(doc, page_index, max_dim=max_dim)
        rendered.append(VisionPage(page_index=page_index, image_bytes=png_bytes))
    return rendered


def iter_pdf_pages(pdf_bytes: bytes, page_numbers: Iterable[int] | None, max_dim: int) -> Iterable[VisionPage]:
    try:
        import fitz  # PyMuPDF
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("pymupdf is required for vision OCR") from exc

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if page_numbers is None:
        page_indices = list(range(len(doc)))
    else:
        page_indices = [max(0, p - 1) for p in page_numbers]
    logger.info("Rendering PDF pages for vision OCR pages=%s", [p + 1 for p in page_indices])
    for page_index in page_indices:
        png_bytes = _render_page_image(doc, page_index, max_dim=max_dim)
        yield VisionPage(page_index=page_index, image_bytes=png_bytes)


def _ollama_generate(settings: Settings, model: str, prompt: str, image_bytes: bytes) -> str:
    base = ollama.base_url(settings)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "images": [base64.b64encode(image_bytes).decode("ascii")],
    }
    logger.info(
        "Ollama vision generate model=%s prompt_chars=%s image_bytes=%s",
        model,
        len(prompt),
        len(image_bytes),
    )
    if __import__("os").getenv("OLLAMA_DEBUG") == "1":
        logger.info("Vision OCR prompt:\n%s", prompt)
    with ollama.client(settings, timeout=settings.vision_ocr_timeout_seconds) as http:
        response = http.post(f"{base}/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        text = str(data.get("response") or "").strip()
        if __import__("os").getenv("OLLAMA_DEBUG") == "1":
            sample = text[:300]
            logger.info("Vision OCR response len=%s sample=%s", len(text), sample)
        else:
            logger.info("Vision OCR response len=%s", len(text))
        return text


def ocr_pdf_pages(
    settings: Settings,
    pdf_bytes: bytes,
    page_numbers: Iterable[int] | None = None,
) -> list[PageText]:
    if not settings.vision_model:
        raise RuntimeError("VISION_MODEL not set")
    ollama.ensure_model(settings, settings.vision_model)
    prompt = load_prompt(settings)
    results: list[PageText] = []
    count = 0
    for page in iter_pdf_pages(pdf_bytes, page_numbers, max_dim=settings.vision_ocr_max_dim):
        if 0 < settings.vision_ocr_max_pages <= count:
            break
        text = _ollama_generate(settings, settings.vision_model, prompt, page.image_bytes)
        results.append(PageText(page=page.page_index + 1, text=text, source="vision_ocr"))
        count += 1
    logger.info("Vision OCR rendering count=%s max_dim=%s", count, settings.vision_ocr_max_dim)
    logger.info("Vision OCR completed pages=%s", [p.page for p in results])
    return results
