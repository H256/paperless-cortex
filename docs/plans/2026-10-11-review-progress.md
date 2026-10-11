# Plan: Review progress on the dashboard, writeback empty state

Date: 2026-10-11 · Issues: #396, #397 · Series: #398 (list), #399 (feedback), #400 (compare + split view) · Branch: `agent/396-review-progress`

## Goal
The reviewer wants to know when everything has been looked at and suggestions accepted. The dashboard only showed processing coverage (100 %), not review state.

## Design
- `GET /documents/review-summary` walks the library once (same derivation as the list: `apply_derived_fields_and_review_status`) and returns `total`, `reviewed`, `unreviewed`, `needs_review`, `no_correspondent` and `issue_date_is_import_date`. The last two count **unreviewed** documents only (what is left). Cached via the existing short-lived list cache, invalidated with it.
- Pure counting lives in `services/documents/review_summary.py` (`summarize_review_rows`); the route only walks and caches.
- Dashboard: "Review progress" card (bar + tiles linking into the filtered list: `review_status`, `correspondent=-1`, `import_date=1`), "Review open documents" button, "All correspondents" collapsed.
- Writeback preview: explicit empty and loading states.
- Documents deleted in Paperless stay in Cortex but are not part of the Paperless listing, so they are not counted.

## Tests
- `tests/test_review_summary.py` (counting), `tests/test_documents_routes.py` (route), `DashboardView.integration.test.ts`, `WritebackDryRunView.integration.test.ts`.

## Not included
- Preset counters in the documents list and per-row badges (#398); busy states (#399); comparison table/split view (#400).
