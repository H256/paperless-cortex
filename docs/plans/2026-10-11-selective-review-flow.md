# Plan: Faster, selective review of Unreviewed / Needs review documents

Date: 2026-10-11 · Branch: `agent/357-358-selective-review-flow` (from `develop`)
Issues: #357 (real links), #358 (selective multi-field apply), #359 (tracking / follow-ups)

## Findings (production UI + code)

- Cards/rows are click handlers (`router.push`), not links → no new tab ([`DocumentCard.vue`](../../frontend/src/components/DocumentCard.vue), [`DocumentsTable.vue`](../../frontend/src/components/DocumentsTable.vue)).
- Every suggestion field is applied through its own confirm dialog + reload ([`DocumentSuggestionsSection.vue`](../../frontend/src/components/DocumentSuggestionsSection.vue)).
- Backend `apply-suggestion` for `tags` **replaces** the tag set (`doc.tags = matched`) and rewrites pending tags ([`suggestion_apply.py`](../../backend/app/services/ai/suggestion_apply.py)). Applying a subset of suggested tags must therefore merge with existing + pending tags on the client.
- The suggestion LLM only sees OCR text, never the image: layout hints are useless; text passages / semantic rules are useful.

## Principles

1. Suggestions are sometimes nonsense → **never preselect, never bulk-accept**. Only checked fields are written.
2. "Suggest new" stays independent of selection and never applies anything.
3. Writes remain local until the existing explicit writeback.

## Slice 1 (this PR)

### A. Real links (#357)
- `DocumentsView` provides `docHref(id, tab?)` (via `router.resolve`, keeping `return_to`).
- `DocumentCard`: title becomes an anchor with a stretched click area; Open/Continue/Review become anchors. Plain left click keeps SPA navigation; modifier/middle click lets the browser open a new tab. Without `docHref` (Similar section) the old emit behavior is kept.
- `DocumentsTable`: title cell and Open/Continue/Review are anchors; row handles Ctrl/Cmd/middle click via `window.open`.

### B. Selective multi-field apply (#358)
- `DocumentSuggestionsSection`: checkbox per field per source (nothing preselected, one source per field), per-tag chips for tags, apply bar with before → after preview, "Apply selected (n)" and "Clear".
- Tags: final value = existing tags ∪ pending tags ∪ selected suggested tags (case-insensitive, de-duplicated).
- `useDocumentSuggestionsApply.applySelected(items)`: sequential, per-item error capture, one reload at the end, returns `{ applied, failed }`.
- `DocumentDetailView`: wires the event and shows a single toast (applied / failed fields).

### Tests
- `useDocumentSuggestionsApply.test.ts`: applySelected happy path, partial failure, single reload.
- New `utils/suggestionSelection.test.ts`: tag merge + selection helpers.
- `DocumentsView.integration.test.ts` keeps passing (open handlers unchanged for plain clicks).

## Out of scope → #359
Review mode (prev/next), deterministic date/correspondent candidates from OCR text, text-passage focus for "Suggest new", OCR source switch, plausibility warnings.
