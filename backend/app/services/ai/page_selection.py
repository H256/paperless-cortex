from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.models import DocumentPageText
from app.services.documents.text_pages import split_text_pages

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_PAGE_SPEC_PART = re.compile(r"^(\d{1,4})(?:\s*-\s*(\d{1,4}))?$")
MAX_PAGE_SPEC_LENGTH = 100


class PageSelectionError(ValueError):
    """The requested pages are malformed or not available for the document."""


def parse_page_spec(spec: str | None) -> list[int] | None:
    """Parse ``"1"``, ``"1-3,5"`` into a sorted, de-duplicated list of 1-based pages.

    ``None``/blank means "no restriction". Anything malformed raises
    :class:`PageSelectionError` so a typo never silently widens the text.
    """
    if spec is None or not spec.strip():
        return None
    if len(spec) > MAX_PAGE_SPEC_LENGTH:
        raise PageSelectionError("Page selection is too long")
    pages: set[int] = set()
    for raw_part in spec.split(","):
        match = _PAGE_SPEC_PART.match(raw_part.strip())
        if not match:
            raise PageSelectionError(f"Invalid page selection: {raw_part.strip() or '(empty)'}")
        first = int(match.group(1))
        last = int(match.group(2)) if match.group(2) else first
        if first < 1 or last < first:
            raise PageSelectionError(f"Invalid page range: {raw_part.strip()}")
        if last - first > 500:
            raise PageSelectionError("Page range is too large")
        pages.update(range(first, last + 1))
    return sorted(pages)


def select_page_text(
    db: Session,
    *,
    doc_id: int,
    source: str,
    pages: list[int],
    content: str | None,
) -> str:
    """Text of exactly the requested pages of one OCR source.

    Uses the stored page texts of ``source``; for ``paperless_ocr`` it falls back to
    the form-feed split of the document content. Raises :class:`PageSelectionError`
    when the document has no page structure or none of the pages exist, instead of
    falling back to the whole text.
    """
    rows = (
        db.query(DocumentPageText)
        .filter(DocumentPageText.doc_id == doc_id, DocumentPageText.source == source)
        .order_by(DocumentPageText.page.asc())
        .all()
    )
    by_page: dict[int, str] = {}
    for row in rows:
        text = (row.clean_text or row.text or "").strip()
        if text:
            by_page[int(row.page)] = text
    if not by_page and source == "paperless_ocr":
        by_page = {page.page: page.text.strip() for page in split_text_pages(content) if page.text.strip()}
    if not by_page:
        raise PageSelectionError("This document has no page structure for the chosen text")
    wanted = [page for page in pages if page in by_page]
    if not wanted:
        raise PageSelectionError(
            f"None of the requested pages exist (document has pages 1-{max(by_page)})"
        )
    return "\n\n".join(by_page[page] for page in wanted)
