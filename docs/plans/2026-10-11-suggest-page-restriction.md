# Plan: Page restriction for "Suggest new"

Date: 2026-10-11 · Issue: #392 · Branch: `agent/392-suggest-page-restriction` (from `develop`)

## Goal
For long documents the model reads the whole OCR text. The date or sender is usually on page 1 (letterhead), while terms, attachments or enclosures on later pages mislead it. The reviewer can restrict "Suggest new" to chosen pages.

## Design
- `pages` (string, e.g. `1`, `1-2,4`) on `POST /documents/{id}/suggestions/field`; forwarded as sorted page list in the queued task (`task["pages"]`).
- `services/ai/page_selection.py`: `parse_page_spec` (strict: digits, ranges, max 100 chars, no `0`, no reversed ranges) and `select_page_text` (stored page texts of the text the model reads; for `paperless_ocr` fallback to the form-feed split of the content).
- No silent widening: malformed specs, documents without page structure, or none of the pages existing raise `PageSelectionError`, which the route answers with 422 **before** anything is queued.
- The page restriction applies to the text the model reads (`text_source` or the panel source). The queued worker applies the same helper.
- UI: "Only these pages (optional)" input in "Guidance for Suggest new", client-side format hint, counts as active guidance.

## Tests
- `tests/test_page_selection.py`: parsing, page lookup, fallbacks, errors, queued task, bad pages never enqueued.
- `tests/test_documents_suggestions_routes.py`: vision/paperless/text_source combos, invalid pages -> 422.
- `tests/test_worker_suggest_field.py`: worker reads only the requested pages.
- `DocumentSuggestionsSection.test.ts`: payload and invalid hint.

## Not included
- Page picker from thumbnails, page restriction for the main (non-"Suggest new") generation.
