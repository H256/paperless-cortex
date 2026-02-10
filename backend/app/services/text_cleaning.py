from __future__ import annotations

import re

_WS_RE = re.compile(r"[ \t]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")
_PAGE_NUM_RE = re.compile(r"^\s*(seite|page)?\s*\d+\s*$", re.IGNORECASE)


def estimate_tokens(text: str | None) -> int:
    if not text:
        return 0
    # Fast, conservative approximation for mixed OCR text.
    return max(1, int(len(text) / 3.5))


def clean_ocr_text(text: str | None) -> str:
    if not text:
        return ""
    cleaned = text
    try:
        import ftfy

        cleaned = ftfy.fix_text(cleaned)
    except Exception:
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
            if current and nxt and not current.endswith((".", ":", ";", "?", "!")):
                if not re.match(r"^[-*•]\s+", nxt):
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

