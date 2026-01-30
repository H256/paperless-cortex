# User Manual (Current Features)

## Overview
Paperless Intelligence is a read‑only companion to Paperless‑ngx. It syncs metadata + OCR text, runs embeddings (including optional Vision OCR), and provides search and suggestions without modifying Paperless.

## Setup
1) Configure `.env` (see `.env.example`)
2) Start backend and frontend
3) (Optional) Run DB migrations

## Documents page
- **Sync (DB only)**: Fetches metadata + OCR from Paperless into Postgres.
- **Reprocess all (sync + embed)**: Forces sync + embeddings; with Vision OCR enabled this reprocesses all pages.
- **Re‑embed current**: Re-embeds either the current page list or all docs depending on “Current page only”.
- **Incremental**: Only pulls documents modified since last sync.
- **Filters**: Sort, correspondent, tag, and date range filters (read‑only).

### Semantic search
- Enter a query and click **Search**.
- **Source filter**: Choose `vision_ocr`, `paperless_ocr`, or `pdf_text`.
- **Dedupe**: Keep best hit per document/page.
- **Rerank**: Prefer results with higher text quality.
- Click a result to open the document detail page.
- **Open in Paperless** opens the source doc in Paperless (requires `VITE_PAPERLESS_BASE_URL`).

## Document detail page
### Text layer (baseline)
- Shows Paperless OCR text.
- **Analyze quality** computes a quality score + metrics for the baseline text.

### Extracted page texts (debug)
- **Load extracted pages** shows per‑page text for:
  - baseline layer (Paperless OCR / pdfminer)
  - vision OCR layer (if available)
- Each page includes a quality score + metrics.
- Vision OCR pages include a PDF preview thumbnail next to the extracted text.
- Use **Show previews** and the size slider to control thumbnails (persisted locally).

### AI suggestions
- **Generate suggestions** runs an LLM and returns:
  - summary
  - suggested title/date/tags/correspondent/document type
  - entities + risks
- Suggestions are read‑only and do not write back to Paperless.
  - Prompt is loaded from `backend/app/prompts/suggestions.txt`
  - Suggestions run twice: baseline OCR and vision OCR (if available)
  - Vision OCR is triggered on-demand when refreshing Vision OCR suggestions
  - Best pick column merges baseline + vision suggestions
  - Per-field variants (title/date/correspondent/tags) can be generated and applied

## Embeddings + OCR layers
- **Baseline layer**: Paperless OCR (or pdfminer per-page text if needed).
- **Vision OCR layer**: Optional; stored separately and embedded with `source=vision_ocr`.
- Each embedded chunk stores `doc_id`, `page`, `source`, `quality_score`.

## Configuration highlights
- `ENABLE_VISION_OCR=1` enables Vision OCR.
- `VISION_MODEL=...` selects the vision model.
- `VISION_OCR_PROMPT_PATH=backend/app/prompts/vision_ocr.txt` sets the prompt file.
- `EMBED_ON_SYNC=1` embeds automatically after sync.

## Auditing
- Suggestion runs and field overrides are written to `suggestion_audit`.

## Queue
- Optional Redis queue for document processing.
- Enable with `QUEUE_ENABLED=1` and `REDIS_HOST=...`.
- UI footer shows current queue length.

## Important notes
- No automatic writeback to Paperless (read‑only).
- If Vision OCR is enabled, reprocessing embeds both baseline and vision layers.
