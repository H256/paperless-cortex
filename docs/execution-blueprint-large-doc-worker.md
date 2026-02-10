# Execution Blueprint: Large Document Worker Processing

## Goal
- Ingest large documents quickly and reliably into DB.
- Prevent LLM timeouts from oversized context.
- Keep suggestions stable and summaries factually useful (with key metadata).

## Priorities
1. Throughput first: page data must land in DB fast.
2. Reliability second: each step resumable/idempotent.
3. Quality third: summaries/suggestions must preserve key facts, dates, entities, numbers.

## Processing Policy by Document Size
- Small (`<20` pages): existing fast path allowed.
- Medium (`20-150` pages): page-first pipeline + section aggregation.
- Large (`>150` pages): strict page-first only, no monolithic summary calls.

## Worker Pipeline (Page-First)
For each page, run independently:
1. `vision_ocr_extract_page`
2. `store_page_raw_text`
3. `clean_page_text`
4. `embed_page_clean_text`
5. `generate_page_notes`

Then per document:
1. `aggregate_section_summaries` (from page notes)
2. `aggregate_global_summary` (from section summaries)
3. `run_suggestions` (budgeted, stable prompt contract)

Notes:
- Replace large batch OCR defaults for big docs with per-page tasks.
- Preserve raw OCR layer; never overwrite.

## Data Model Changes
### Extend `document_page_texts`
- `raw_text` (TEXT): original OCR/VLM output for the page.
- `clean_text` (TEXT): normalized text used for embeddings/LLM.
- `cleaned_at` (String/timestamp style consistent with current schema).
- `token_estimate_raw` (INT, optional).
- `token_estimate_clean` (INT, optional).
- `processing_status` (optional enum/string per step if preferred in same table).

### New `document_page_notes`
- `doc_id` (FK), `page` (INT), `source` (`paperless_ocr`|`vision_ocr`)
- `notes_json` (JSON/TEXT)
- `model_name`, `processed_at`, `status`, `error`

### New `document_section_summaries`
- `doc_id` (FK), `section_key` (e.g. `1-25`)
- `summary_json` (JSON/TEXT)
- `model_name`, `processed_at`, `status`, `error`

## Queue & Orchestration
- Use granular tasks: `doc_id + page + step`.
- Use a composing orchestrator only to enqueue next step(s), not to do all heavy work inline.
- Keep strict idempotency:
  - Upsert by `(doc_id, page, source)` keys.
  - Skip completed steps unless `force=1`.
- Fair scheduling:
  - Small tasks prioritized.
  - Aging rule prevents starvation of large docs.

## Token & Timeout Budgeting
## Preflight estimation
- Fast estimator (CPU-first): chars-to-token heuristic (`tokens ~= chars / 3.5`, configurable).
- Optional precise estimator when available for model family.

## Hard limits (defaults)
- `MAX_INPUT_TOKENS_PER_CALL=6000`
- `MAX_OUTPUT_TOKENS_PAGE_NOTES=300`
- `MAX_OUTPUT_TOKENS_SECTION=600`
- `MAX_OUTPUT_TOKENS_GLOBAL=900`
- `MAX_PAGES_PER_SECTION=25`
- `LLM_TIMEOUT_PAGE_NOTES=45s`
- `LLM_TIMEOUT_SECTION=90s`
- `LLM_TIMEOUT_GLOBAL=120s`
- `MAX_RETRIES=2`

## Downgrade strategy (automatic)
1. Timeout/overflow -> reduce section size (e.g. `25 -> 12 -> 6`).
2. Reduce output token target.
3. Keep mandatory fields only (facts/entities/numbers/dates).
4. Mark partial status; continue pipeline.

## Summary Quality Contract
Every summary layer must output structured JSON with:
- `key_facts`
- `key_dates`
- `key_entities`
- `key_numbers`
- `open_questions`
- `confidence_notes`

Validation:
- Reject invalid JSON.
- Re-ask once with strict repair prompt.
- If still invalid: store error + fallback minimal extraction.

## Suggestions Stability Contract
- Suggestions must always include: title/date/correspondent/tags/summary.
- Input is budgeted clean text, never unbounded full document dump.
- For large docs:
  - build suggestions from section-level distilled context + top relevant page notes
  - avoid sending full concatenated page text

## Embedding Strategy
- Embed only `clean_text` (primary retrieval layer).
- Optional second layer later: embed `page_notes` for QA recall.
- Use small request batches and chunk upserts to avoid payload spikes.

## CPU-Fast Python Modules for Cleanup
- `ftfy`: OCR character fixes and Unicode normalization.
- `rapidfuzz`: repeated header/footer detection across pages.
- `re` (stdlib): hyphenation and line-wrap normalization.
- `orjson`: fast JSON serialization for notes/summaries payloads.
- Optional: `regex` only if advanced patterns are required.

## Observability & Acceptance
## Metrics
- Pages ingested/minute
- Step latency p50/p95 (`ocr`, `clean`, `embed`, `notes`, `section`, `global`, `suggestions`)
- LLM timeout rate by step/model
- Retry rate
- Partial/failure counts

## Done criteria
1. Large docs are ingested to DB without worker stalls.
2. Timeout rate significantly reduced for docs `>20` pages.
3. Suggestions remain schema-stable and non-empty.
4. Global summaries contain key facts/dates/entities/numbers from section evidence.

## Rollout Plan
1. Phase A: Introduce page-first ingestion + DB schema + budgets (summaries unchanged).
2. Phase B: Add page notes + section/global hierarchy.
3. Phase C: Route suggestions to distilled context for large docs.
4. Phase D: Tune thresholds from live metrics.

