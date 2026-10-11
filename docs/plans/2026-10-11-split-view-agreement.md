# Plan: Split view and agreement indicator (slice 1 of #400)

Date: 2026-10-11 · Issue: #400 · Branch: `agent/400-split-view` (from `develop`)

## Goal
The reviewer verifies suggestions against the document. The PDF sat below all suggestions, and the three source panels had to be compared by eye.

## Design
- **Split view** (`xl` and up, Suggestions tab only): tabs + content left, PDF right (sticky, scrollable). Toggle "Side by side" next to the tabs, remembered in `localStorage` (`document_detail_split_view`, default on). Narrow screens and other tabs stay stacked.
- **Agreement indicator**: pure util `suggestionAgreement.ts` compares title, date and correspondent across Vision OCR, Paperless OCR (and similar docs for the correspondent) plus the deterministic text candidates. Values are normalized (case, punctuation, whitespace; dates to the ISO day). Badge per value: `n / total agree` or `Only this source`; nothing when fewer than two sources carry a value.
- Selection and "Apply selected" are unchanged: nothing is preselected or applied automatically.

## Tests
- `suggestionAgreement.test.ts`, `DocumentSuggestionsSection.test.ts` (badges, text as source), `DocumentDetailView.integration.test.ts` (split layout, toggle, stacked on other tabs).

## Next slices of #400
- Comparison table (one row per field, columns Current | Vision | Paperless | Similar) with per-cell "Suggest new".
- Candidate click highlights/jumps to the page in the PDF.
