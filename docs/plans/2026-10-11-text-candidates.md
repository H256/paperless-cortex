# Plan: Deterministic date and correspondent candidates

Date: 2026-10-11 · Issue: #373 · Tracking: #359 · Branch: `agent/373-text-candidates` (from `develop`)

## Goal
Issue date and sender are often not recognized reliably, and LLM suggestions for them are sometimes wrong. The suggestion LLM only sees OCR text, so rules over the same text are a cheap, predictable second opinion that the reviewer can pick from.

## Design
- **No LLM, no side effects.** `GET /documents/{id}/suggestions/candidates` reads cached page texts (`document_page_texts`, fallback `Document.content`); it never triggers OCR, LLM calls or queue work.
- **Dates** (`backend/app/services/ai/text_candidates.py`): numeric `dd.mm.yyyy`, `dd-mm-yyyy`, `dd/mm/yyyy` (month-first only when the numbers make it unambiguous, e.g. `09/20/2026`), `yyyy-mm-dd` / `yyyy/mm/dd`, `dd.mm.yy` (dots only), and written months in German, English, French, Spanish, Italian, Dutch, Portuguese, Polish and Czech incl. ordinals and "de"/"of" ("20th of September", "20 de septiembre de 2026", "September 20, 2026"). Keywords for issue/delivery/due/period/birth/print exist in the same languages. Values like `2026-09-20-001` (invoice numbers) are not dates. Dates are classified by the keyword **closest** to the date (issue / delivery / due / period / other); birth dates are dropped, years before 1950 and dates more than a year in the future are dropped. Score = label weight + early-occurrence boost + page 1 boost + small repetition bonus.
- **Correspondents**: known names are matched against the first 30 lines (exact, all tokens, fuzzy ratio >= 0.86) and the full text; e-mail/website domains are a weaker signal; legal forms and punctuation are ignored. At most one unknown name is proposed from a header line with a legal form (`known: false`).
- **Sources are merged**: each OCR source (vision, paperless) is evaluated separately; occurrences are not added across sources, the best score wins and the sources are listed.
- **UI**: a "Candidates from text" block in the Suggestions tab; clicking a candidate selects it for the field (source `text_candidates`) and uses the same "Apply selected" flow. Nothing is preselected and nothing is applied automatically.

## Tests
- `backend/tests/test_text_candidates.py`: ranking, nearest-keyword labelling, formats, invalid/future/birth dates, correspondent matching, legal forms, domains.
- `backend/tests/test_documents_suggestions_routes.py`: route with stored texts, content fallback, 404.
- `DocumentSuggestionsSection.test.ts`: rendering, selection, emitted apply items.

## Not included
- Per-correspondent learned rules, IBAN/invoice-number extraction, passage focus for "Suggest new" (tracked in #359).
