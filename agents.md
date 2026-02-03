# Paperless Intelligence Layer (Arcane)

## Mission
Build a separate "intelligence" project that augments Paperless-ngx with:
- AI-generated structured metadata (entities, dates, doc type, risks, etc.)
- embeddings + semantic search + reasoning chat
- citations with PDF highlights (page plus bounding boxes when available)
- a strict safety model: read-only by default, explicit manual writeback only

The project runs as a separate stack on host "Arcane" (Docker). Paperless itself is a separate stack and must not be modified.

## High-level design (current)
Paperless-ngx remains the source of truth. This project:
1) reads metadata + OCR text from Paperless API (Token auth)
2) optionally fetches PDF pages for highlighting or vision-based OCR fallback
3) runs LLM analysis (remote Ollama server)
4) stores results in Postgres plus embeddings in Qdrant
5) provides a FastAPI backend plus Vue frontend for inspection and manual, per-field writeback

## Constraints / Non-goals
- No automatic writeback to Paperless. Default is read-only.
- Writeback must be explicit per-document and per-field:
  - Title, Tags, Correspondent, Document Date (each independently)
  - Optional summary note writeback (manual button), wrapped in markers
- Never delete or modify original Paperless content.
- Keep an audit log for every writeback (who, when, what, old vs. new).
- Store alternative OCR as an additional layer, never overwrite Paperless baseline OCR.

## Deployment / Infrastructure
- Host: Arcane (Linux), Docker Compose.
- Data persistence: local bind-mounts under project folder:
  - ./data/postgres, ./data/qdrant, ./data/redis (optional)
- External network: all callable components must join `traefik-public`.
- qdrant is exposed via Traefik and reachable by LAN DNS (Pi-hole):
  - qdrant.elysium.lan -> Arcane IP
- Postgres/Redis are exposed only via LAN ports (bound to Arcane LAN IP) and must be firewalled to the dev machine if used remotely.
- Ollama is hosted on another server (more compute) and is accessed via HTTP (base URL configurable).

## Components (current stack)
- Postgres (metadata, OCR alternative layers, suggestions, audit)
- Qdrant (embeddings + chunk metadata)
- Redis (queue + worker lock)

### Application layer
- FastAPI backend:
  - Read-only API for documents, tags, correspondents, document types, and connections
  - Manual writeback endpoints (per-field, per-doc)
  - Queue management endpoints (peek/reorder/move-top/move-bottom/pause/reset)
  - Processing utilities: dry-run missing-work summary, reset intelligence data, mark missing Paperless docs
- Vue 3 (Vite, Composition API) frontend:
  - Read-only views: doc list, doc details, semantic search, chat UI, queue manager
  - Manual writeback buttons per doc plus per field
  - PDF viewer with highlight overlays (PDF.js attempted; CSP-safe preview fallback active)

## Paperless integration
### Auth
- Paperless API uses Token authentication:
  - Header: Authorization: Token <token>

### Data ingestion
- Fetch list of documents and metadata from Paperless API:
  - document id, title, created/modified, tags, correspondent, doc type, document date, etc.
- Fetch OCR text layer from Paperless (preferred baseline):
  - avoid re-OCR by default; Paperless already has OCR text
- Fetch PDF only when needed:
  - for highlighting in UI
  - for second OCR pass (vision) on low-quality pages
  - for layout-dependent extraction
  - for PDF preview rendering when CSP blocks PDF.js

### Sync strategy
- Continue-processing syncs new docs and enqueues only missing tasks.
- Reprocess-all clears intelligence data and rebuilds.
- Local edits are preserved; insert-only sync avoids overwriting.

## Second OCR (vision fallback)
### Goal
Improve recognition for cases where Paperless OCR is poor. Do not replace baseline; store as an alternate layer.

### Current approach
1) Score OCR quality using heuristics (length, non-alnum ratio, score)
2) Re-OCR only problematic pages (not whole PDF)
3) Store results as alternate layer (source="vision_ocr", page, text, model, processed_at)
4) Merge strategy: Paperless OCR is baseline; Vision OCR is fallback for analysis/search

## Embeddings + search
- Chunk text into ~500--1000 token blocks.
- Store in Qdrant with payload:
  - doc_id, chunk_id, page (if known), bbox (if known), text snippet, source layer
- Use embeddings for:
  - similar documents
  - semantic search
  - retrieval for chat

### Current state (highlights)
- PDF text extraction uses PyMuPDF word boxes when available and stores bbox per chunk in Qdrant.
- Vision OCR pages are stored in DB (text only); embeddings reuse stored vision text.
- Chat/Search citations deep-link to document viewer with page + bbox (when available).
- PDF.js viewer exists; CSP-safe fallback uses server-side page preview image with highlight overlay.

### Citations
Chat responses must include citations as structured references:
- doc_id, page, and bbox if available (preferred)
- If bbox not available, at least doc_id + page
UI must be able to:
- fetch PDF from Paperless
- render pages and overlay highlights using coordinates (pdf.js + overlay)

## Chat / Reasoning search
### Pipeline
1) User question
2) Retrieve top-k chunks from Qdrant
3) LLM answers with:
   - final answer
   - cited passages (doc_id/page/bbox references)
4) UI renders:
   - answer
   - clickable citations that navigate PDF and highlight areas

### Current state
- Citations carry bbox when chunked from PDF text; highlight overlay is shown in the viewer.

## Manual writeback to Paperless
### What is allowed
Per document, via explicit user action:
- Update title
- Update tags
- Update correspondent
- Update document date
- Add a summary note (as a Note/Comment in Paperless)

### Summary note formatting
All AI summaries stored in Paperless notes must be bracketed for easy detection:
- AI_SUMMARY v1 --
...summary text...
- /AI_SUMMARY -

### Audit logging
Every writeback must be stored locally:
- doc_id, field, old value, new value, timestamp, user

## API ideas (backend)
- GET /documents
- GET  /documents/{id}
- POST /documents/{id}/sync
- POST /documents/{id}/analyze
- POST /documents/{id}/second-ocr
- POST /chat
- POST /documents/{id}/writeback (explicit per-field actions)

### New endpoints (implemented)
- POST /documents/process-missing (summary + enqueue missing work)
- POST /documents/reset-intelligence (clear embeddings/page texts/suggestions)
- POST /documents/clear-intelligence (wipe local documents + intelligence data)
- POST /documents/delete-vision-ocr /delete-suggestions /delete-embeddings
- GET /documents/{id}/pdf (proxy PDF bytes)
- Queue: POST /queue/move-top, POST /queue/move-bottom

## Configuration
Environment variables (examples):
- PAPERLESS_BASE_URL=https://paperless.elysium.lan
- PAPERLESS_API_TOKEN=...
- OLLAMA_BASE_URL=http://<ollama-host>:11434
- EMBEDDING_MODEL=qwen3-embedding
- DATABASE_URL=postgres://...
- QDRANT_URL=https://qdrant.elysium.lan (or internal http://qdrant:6333)
- QDRANT_API_KEY optional (future hardening)
- QDRANT_COLLECTION=paperless_chunks
- EMBED_ON_SYNC=1
- CHUNK_MODE=heuristic
- CHUNK_MAX_CHARS=1200
- CHUNK_OVERLAP=200
- CHUNK_SIMILARITY_THRESHOLD=0.75

## Repo layout
- /backend: FastAPI service (Python, uv)
- /frontend: Vue 3 + Vite SPA (Composition API)

## Local development
### Backend
- cd backend
- uv sync
- uv run uvicorn app.main:app --reload --port 8000

### Migrations (Alembic)
- cd backend
- uv sync
- uv run alembic revision --autogenerate -m "init"
- uv run alembic upgrade head

### Frontend
- cd frontend
- npm install
- npm run dev

### Dev URLs
- Backend: http://localhost:8000
- Frontend: http://localhost:5173

## MVP Definition of Done (achieved)
- Compose stack runs on Arcane: Postgres + Qdrant (+optional Redis), persistent in ./data
- Dev machine can reach:
  - Qdrant via https://qdrant.elysium.lan (Traefik)
  - Postgres via arcane-ip:5432 (LAN, firewalled) or via SSH tunnel
- Basic data model + sync script exists (even minimal):
  - can fetch doc list plus OCR text from Paperless and store metadata
- Embedding ingestion works: chunks stored in Qdrant with doc_id payload
- Simple query endpoint returns top matches with citations (doc_id/page)

## Current UX (processing) (achieved)
- "Continue processing" runs a dry-run, shows missing-work summary, and enqueues only missing tasks.
- "Reprocess all" clears intelligence data and rebuilds (explicit confirmation).
- Queue UI supports reorder + move top/bottom, and bulk enqueue is batched to avoid Redis socket exhaustion.

## LLM Configuration

### Ollama Server
- Ollama runs on a separate AI server (not on Arcane).
- It is accessed via HTTP.
- Base URL must be configurable via environment variable.

Environment:
- OLLAMA_BASE_URL=http://<ollama-host>:11434

### Primary Model
- Default reasoning / extraction / chat model:
  - MODEL_NAME=gpt-oss:20b
- Default-Model for Vectorization:
- VECTORIZATION_MODEL=snowflake-arctic-embed2

This model is used for:
- Structured document analysis (JSON output)
- Entity extraction
- Risk classification
- Cross-document reasoning
- Chat answers with citations

### Embedding Model
- EMBEDDING_MODEL=nomic-embed-text
(or configurable via EMBEDDING_MODEL env variable)

### Optional Vision Model (for the second OCR pass)
- VISION_MODEL=qwen2.5-vl
(or configurable)

Vision model is used only for:
- Re-OCR of low-quality pages
- Extracting bounding boxes when needed

### Performance Notes
- gpt-oss:120b is large and may require:
  - Increased request timeout (e.g., 120--300 seconds)
  - Streaming support in the API layer
  - Retry logic for long reasoning tasks

All model names must be configurable via environment variables.

## Ausbaustufe: On-the-fly strukturierte Antworten (MVP)
- Intent-Analyse je Frage (Trend/Zeitleiste, Fakten-Lookup, Latest-Event).
- Retriever + Reranking auf max. 10 Dokumente pro Anfrage.
- Pro-Dokument Extraktion in kleines JSON-Schema passend zur Frage (z.B. Preis/Zeitraum, Laborwert/Datum).
- Aggregation/Reasoning zur Laufzeit (Trends, %-Änderungen, Latest-Event).
- Antwortformat dynamisch anhand der Frage (Text, Vergleich, Kurz-Timeline).
- Quellen immer mit Doc-ID + Seitenangabe ausgeben (ohne persistente Tabellen).
- Phase 2 (optional): Evidence-Locator mit Vision-OCR-Text + BBox-Highlighting.

## Roadmap (short)
- Client refactor: extract logic from `views/*.vue` into composables/stores and shared components.
- Server refactor: consolidate queue/task logic and standardize error handling.

## Recent changes (2026-02-02 to 2026-02-03)
- Continue-processing: sync progress modal, enqueue summary toast, batch limit slider.
- Missing-work logic: only enqueue missing items; vision embedding source tracked.
- Operations page: destructive actions + wipe local data + runtime config + copy buttons.
- UX: local overrides shown, badges + tooltips, suggestion metadata surfaced.
- Queue: ETA display, last run timestamp, reset counters when idle.
