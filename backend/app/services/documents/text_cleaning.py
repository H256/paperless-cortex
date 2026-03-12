from __future__ import annotations

import html
import re

_WS_RE = re.compile(r"[ \t]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")
_PAGE_NUM_RE = re.compile(r"^\s*(seite|page)?\s*\d+\s*$", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")
_HTML_ANY_RE = re.compile(r"<[^>]+>")
_HTML_SCRIPT_STYLE_RE = re.compile(r"<\s*(script|style)\b[^>]*>.*?<\s*/\s*\1\s*>", re.IGNORECASE | re.DOTALL)
_HTML_BR_RE = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)
_HTML_BLOCK_CLOSE_RE = re.compile(
    r"<\s*/\s*(p|div|li|ul|ol|h[1-6]|tr|table|section|article)\s*>",
    re.IGNORECASE,
)
_HTML_ROW_OPEN_RE = re.compile(r"<\s*tr\b[^>]*>", re.IGNORECASE)
_HTML_CELL_CLOSE_RE = re.compile(r"<\s*/\s*t[dh]\s*>", re.IGNORECASE)
_TABLE_PIPE_CLEAN_RE = re.compile(r"\s*\|\s*")


def estimate_tokens(text: str | None) -> int:
    if not text:
        return 0
    # Fast, conservative approximation for mixed OCR text.
    return max(1, int(len(text) / 3.5))


def _looks_like_html(text: str) -> bool:
    if "<" not in text or ">" not in text:
        return False
    return bool(_HTML_TAG_RE.search(text))


def _html_to_text(text: str) -> str:
    stripped = _HTML_SCRIPT_STYLE_RE.sub(" ", text)
    stripped = _HTML_BR_RE.sub("\n", stripped)
    stripped = _HTML_ROW_OPEN_RE.sub("\n", stripped)
    stripped = _HTML_CELL_CLOSE_RE.sub(" | ", stripped)
    stripped = _HTML_BLOCK_CLOSE_RE.sub("\n", stripped)
    stripped = _HTML_ANY_RE.sub(" ", stripped)
    stripped = html.unescape(stripped)
    stripped = _TABLE_PIPE_CLEAN_RE.sub(" | ", stripped)
    stripped = re.sub(r"(?:\s*\|\s*){2,}", " | ", stripped)
    return stripped


def clean_ocr_text(text: str | None) -> str:
    if not text:
        return ""
    cleaned = text
    if _looks_like_html(cleaned):
        cleaned = _html_to_text(cleaned)
    try:
        import ftfy

        cleaned = ftfy.fix_text(cleaned)
    except ImportError:
        pass
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    lines = cleaned.split("\n")

    # Remove standalone page number lines.
    filtered_lines: list[str] = []
    for line in lines:
        if _PAGE_NUM_RE.match(line.strip()):
            continue
        filtered_lines.append(line)

    joined: list[str] = []
    i = 0
    while i < len(filtered_lines):
        current = filtered_lines[i].rstrip()
        if i + 1 < len(filtered_lines):
            nxt = filtered_lines[i + 1].lstrip()
            # De-hyphenate wrapped words at line end.
            if current.endswith("-") and nxt and nxt[:1].isalpha():
                current = current[:-1] + nxt
                i += 2
                joined.append(current)
                continue
            # Join hard line wraps for plain text lines.
            if (
                current
                and nxt
                and not current.endswith((".", ":", ";", "?", "!"))
                and not re.match(r"^[-*•]\s+", nxt)
            ):
                current = f"{current} {nxt}"
                i += 2
                joined.append(current)
                continue
        joined.append(current)
        i += 1

    normalized = "\n".join(joined)
    normalized = _WS_RE.sub(" ", normalized)
    normalized = _MULTI_NL_RE.sub("\n\n", normalized)
    return normalized.strip()
