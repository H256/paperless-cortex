from __future__ import annotations

from io import BytesIO
import logging
import re
from dataclasses import dataclass
from typing import Callable

from app.config import Settings
from app.services import vision_ocr
from app.services.page_types import PageText, WordBox

logger = logging.getLogger(__name__)


def split_text_pages(text: str | None) -> list[PageText]:
    if not text:
        return []
    if "\f" not in text:
        return []
    parts = [part.strip() for part in text.split("\f")]
    pages = [p for p in parts if p]
    if len(pages) <= 1:
        return []
    return [PageText(page=i + 1, text=page_text, source="paperless_ocr") for i, page_text in enumerate(pages)]


def extract_pdf_text_pages(pdf_bytes: bytes) -> list[PageText]:
    try:
        import fitz  # PyMuPDF
    except Exception:
        fitz = None

    if fitz is not None:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages: list[PageText] = []
        logger.info("PDF text extraction (pymupdf) pages=%s", len(doc))
        for page_idx in range(len(doc)):
            page = doc.load_page(page_idx)
            rect = page.rect
            width = float(rect.width) or 1.0
            height = float(rect.height) or 1.0
            words = page.get_text("words") or []
            words_sorted = sorted(words, key=lambda w: (round(w[1], 1), w[0]))
            word_boxes = []
            for word in words_sorted:
                text = str(word[4]).strip()
                if not text:
                    continue
                x0, y0, x1, y1 = float(word[0]), float(word[1]), float(word[2]), float(word[3])
                word_boxes.append(
                    WordBox(
                        text=text,
                        bbox=(
                            x0 / width,
                            y0 / height,
                            x1 / width,
                            y1 / height,
                        ),
                    )
                )
            if word_boxes:
                page_text = " ".join(word.text for word in word_boxes).strip()
                pages.append(
                    PageText(
                        page=page_idx + 1,
                        text=page_text,
                        source="pdf_text",
                        words=word_boxes,
                    )
                )
            else:
                text = page.get_text("text") or ""
                pages.append(PageText(page=page_idx + 1, text=text.strip(), source="pdf_text"))
        return pages

    try:
        from pdfminer.high_level import extract_text
        from pdfminer.pdfpage import PDFPage
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("pdfminer.six is required for PDF page extraction") from exc

    pages: list[PageText] = []
    buffer = BytesIO(pdf_bytes)
    page_count = sum(1 for _ in PDFPage.get_pages(buffer))
    logger.info("PDF text extraction (pdfminer) pages=%s", page_count)
    for page_idx in range(page_count):
        buffer.seek(0)
        text = extract_text(buffer, page_numbers=[page_idx]) or ""
        pages.append(PageText(page=page_idx + 1, text=text.strip(), source="pdf_text"))
    return pages


def is_low_quality_text(text: str, min_chars: int, max_non_alnum_ratio: float) -> bool:
    cleaned = text.strip()
    if len(cleaned) < min_chars:
        return True
    alnum = sum(ch.isalnum() for ch in cleaned)
    if alnum == 0:
        return True
    non_alnum_ratio = 1.0 - (alnum / max(1, len(cleaned)))
    return non_alnum_ratio > max_non_alnum_ratio


@dataclass(frozen=True)
class TextQuality:
    score: int
    reasons: list[str]
    metrics: dict[str, float]


def _safe_div(n: float, d: float) -> float:
    return n / d if d else 0.0


def score_text_quality(text: str, settings: Settings) -> TextQuality:
    cleaned = text.strip()
    if not cleaned:
        return TextQuality(score=0, reasons=["empty"], metrics={"length": 0.0})

    length = len(cleaned)
    words = re.findall(r"[A-Za-z0-9ÄÖÜäöüß]+", cleaned)
    word_count = len(words)
    unique_words = len(set(w.lower() for w in words))
    letters = sum(ch.isalpha() for ch in cleaned)
    digits = sum(ch.isdigit() for ch in cleaned)
    alnum = sum(ch.isalnum() for ch in cleaned)
    vowels = set("aeiouAEIOUäöüÄÖÜ")
    vowel_count = sum(ch in vowels for ch in cleaned)
    vowel_ratio = _safe_div(vowel_count, max(1, letters))
    non_alnum_ratio = 1.0 - _safe_div(alnum, length)
    alpha_ratio = _safe_div(letters, length)
    digit_ratio = _safe_div(digits, length)
    no_vowel_tokens = sum(1 for w in words if not any(ch in vowels for ch in w))
    no_vowel_token_ratio = _safe_div(no_vowel_tokens, word_count)
    wordlike_tokens = sum(1 for w in words if any(ch in vowels for ch in w))
    wordlike_ratio = _safe_div(wordlike_tokens, word_count)
    short_tokens = sum(1 for w in words if len(w) <= 2)
    short_token_ratio = _safe_div(short_tokens, word_count)
    avg_word_len = _safe_div(sum(len(w) for w in words), word_count)
    unique_ratio = _safe_div(unique_words, word_count)
    max_run = 1
    run = 1
    for i in range(1, length):
        if cleaned[i] == cleaned[i - 1]:
            run += 1
            if run > max_run:
                max_run = run
        else:
            run = 1

    score = 100
    reasons: list[str] = []

    if length < settings.vision_ocr_min_chars:
        score -= 30
        reasons.append("too_short")
    if non_alnum_ratio > settings.vision_ocr_max_non_alnum_ratio:
        score -= 25
        reasons.append("high_non_alnum")
    if alpha_ratio < 0.2:
        score -= 15
        reasons.append("low_alpha_ratio")
    if vowel_ratio < 0.25 and letters > 20:
        score -= 15
        reasons.append("low_vowel_ratio")
    if digit_ratio > 0.6:
        score -= 10
        reasons.append("high_digit_ratio")
    if avg_word_len < 2.2 or avg_word_len > 12:
        score -= 10
        reasons.append("odd_word_length")
    if short_token_ratio > 0.5 and word_count > 10:
        score -= 10
        reasons.append("many_short_tokens")
    if unique_ratio < 0.3 and word_count > 10:
        score -= 10
        reasons.append("low_unique_ratio")
    if wordlike_ratio < 0.6 and word_count > 10:
        score -= 15
        reasons.append("low_wordlike_ratio")
    if no_vowel_token_ratio > 0.4 and word_count > 10:
        score -= 10
        reasons.append("many_no_vowel_tokens")
    if max_run >= 12:
        score -= 10
        reasons.append("long_repeats")

    score = max(0, min(100, score))
    metrics = {
        "length": float(length),
        "word_count": float(word_count),
        "unique_ratio": float(unique_ratio),
        "alpha_ratio": float(alpha_ratio),
        "digit_ratio": float(digit_ratio),
        "non_alnum_ratio": float(non_alnum_ratio),
        "vowel_ratio": float(vowel_ratio),
        "wordlike_ratio": float(wordlike_ratio),
        "no_vowel_token_ratio": float(no_vowel_token_ratio),
        "avg_word_len": float(avg_word_len),
        "short_token_ratio": float(short_token_ratio),
        "max_run": float(max_run),
    }
    return TextQuality(score=score, reasons=reasons, metrics=metrics)


def _select_vision_pages(settings: Settings, pages: list[PageText]) -> list[int]:
    low_quality_pages: list[int] = []
    for page in pages:
        quality = score_text_quality(page.text, settings)
        logger.info(
            "Page quality doc_page=%s score=%s reasons=%s metrics=%s",
            page.page,
            quality.score,
            quality.reasons,
            quality.metrics,
        )
        if quality.score < settings.vision_ocr_min_score:
            low_quality_pages.append(page.page)
    logger.info("Vision OCR quality check low_quality_pages=%s", low_quality_pages)
    return low_quality_pages


def get_page_text_layers(
    settings: Settings,
    content: str | None,
    fetch_pdf_bytes: Callable[[], bytes] | None,
    force_full_vision: bool = False,
) -> tuple[list[PageText], list[PageText]]:
    baseline_pages = split_text_pages(content)
    if baseline_pages:
        logger.info("Page split using form-feed pages=%s", len(baseline_pages))
    pdf_bytes: bytes | None = None
    if not baseline_pages and (settings.enable_pdf_page_extract or settings.enable_vision_ocr):
        if fetch_pdf_bytes is None:
            logger.info("PDF fetch callback missing")
        else:
            try:
                pdf_bytes = fetch_pdf_bytes()
                logger.info("Fetched PDF bytes=%s", len(pdf_bytes))
            except Exception as exc:
                logger.warning("Failed to fetch PDF bytes: %s", exc)
                pdf_bytes = None
        if pdf_bytes and settings.enable_pdf_page_extract:
            try:
                baseline_pages = extract_pdf_text_pages(pdf_bytes)
                logger.info("Extracted PDF text pages=%s", len(baseline_pages))
            except Exception as exc:
                logger.warning("PDF text extraction failed: %s", exc)
                baseline_pages = []

    vision_pages: list[PageText] = []
    if settings.enable_vision_ocr:
        if not settings.vision_model:
            logger.warning("VISION_MODEL not set; skipping vision OCR")
        elif pdf_bytes is None:
            if fetch_pdf_bytes is not None:
                try:
                    pdf_bytes = fetch_pdf_bytes()
                    logger.info("Fetched PDF bytes=%s", len(pdf_bytes))
                except Exception as exc:
                    logger.warning("Failed to fetch PDF bytes: %s", exc)
                    pdf_bytes = None
        if pdf_bytes:
            try:
                if force_full_vision:
                    page_numbers = [page.page for page in baseline_pages] or None
                    logger.info("Vision OCR full reprocess pages=%s", page_numbers or "all")
                else:
                    page_numbers = _select_vision_pages(settings, baseline_pages) if baseline_pages else None
                    logger.info("Vision OCR selective pages=%s", page_numbers or "all")
                if page_numbers is None or page_numbers:
                    vision_pages = vision_ocr.ocr_pdf_pages(
                        settings,
                        pdf_bytes,
                        page_numbers=page_numbers,
                    )
            except Exception as exc:
                logger.warning("Vision OCR failed: %s", exc)

    return baseline_pages, vision_pages


def get_baseline_page_texts(
    settings: Settings,
    content: str | None,
    fetch_pdf_bytes: Callable[[], bytes] | None,
) -> list[PageText]:
    baseline_pages = split_text_pages(content)
    if baseline_pages:
        logger.info("Page split using form-feed pages=%s", len(baseline_pages))
        return baseline_pages
    if not settings.enable_pdf_page_extract:
        return []
    if fetch_pdf_bytes is None:
        return []
    try:
        pdf_bytes = fetch_pdf_bytes()
        logger.info("Fetched PDF bytes=%s", len(pdf_bytes))
    except Exception as exc:
        logger.warning("Failed to fetch PDF bytes: %s", exc)
        return []
    try:
        baseline_pages = extract_pdf_text_pages(pdf_bytes)
        logger.info("Extracted PDF text pages=%s", len(baseline_pages))
    except Exception as exc:
        logger.warning("PDF text extraction failed: %s", exc)
        baseline_pages = []
    return baseline_pages


def get_page_texts(
    settings: Settings,
    content: str | None,
    fetch_pdf_bytes: Callable[[], bytes] | None,
) -> list[PageText]:
    baseline_pages, vision_pages = get_page_text_layers(
        settings,
        content,
        fetch_pdf_bytes,
        force_full_vision=False,
    )
    if not baseline_pages and not vision_pages:
        if not settings.enable_pdf_page_extract and not settings.enable_vision_ocr:
            logger.info("Page extraction disabled")
        return []
    return baseline_pages + vision_pages
