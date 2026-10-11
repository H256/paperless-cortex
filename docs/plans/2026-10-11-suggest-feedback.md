# Plan: Visible feedback while "Suggest new" runs (slice 1 of #399)

Date: 2026-10-11 · Issue: #399 · Branch: `agent/399-feedback` (from `develop`)

## Findings
- With the queue enabled, "Suggest new" returns `queued` and the UI polls the variant store. The store already holds the **previous** batch (also by design since #387), so the first poll returned the old variants as if they were new, and the real result never appeared.
- Polling gave up silently after ~12 s, shorter than a typical LLM run: the spinner stopped and nothing was shown.
- "Refresh" had no busy indicator.

## Design
- `GET /documents/{id}/suggestions/field/variants` and the queued POST response carry `updated_at` (the batch's `processed_at`). The queued POST returns the stamp that was current at enqueue time.
- Frontend polls every 1.5 s for up to 120 s and only accepts a batch whose stamp differs from the baseline (fallback for servers without the field).
- While waiting, the button shows `Generating... 12s`.
- After the timeout an explicit message says the model is still working and points to the Queue.
- "Refresh" shows a spinner and `Refreshing...`.

## Tests
- `tests/test_variant_stamp.py`, `useDocumentSuggestions.test.ts` (stale batch ignored, first batch accepted, timeout message, direct path).

## Next slices of #399
- Status pill that names the running task, skeleton states for tab content, success hints after apply.
