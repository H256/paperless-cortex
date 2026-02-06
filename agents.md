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
3) runs LLM analysis (OpenAI-compatible LLM servers)
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
- LLM servers are hosted on separate machines (more compute) and are accessed via HTTP (base URLs configurable).

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
- LLM_BASE_URL=http://<llm-host>:8080
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

### LLM Servers (OpenAI-compatible)
- LLMs run on separate AI servers (not on Arcane).
- Accessed via HTTP with OpenAI-compatible endpoints.
- Base URLs must be configurable via environment variables.

Environment:
- LLM_BASE_URL=http://<llm-host>:8080

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
- Phase 2a (MVP, on-the-fly): Für zitierte Seiten Layout-OCR on-demand ausführen, Snippet matchen, BBox aggregieren, sonst fallback auf Doc-ID + Seite.

### Phase 2a Umsetzungsskizze (on-the-fly BBox)
- Backend: neuer Chat-Postprozess-Schritt `resolve_evidence` (nach LLM-Antwort).
- Eingabe: Liste von Zitaten {doc_id, page, snippet} + optional `max_pages=3`.
- Pro Seite:
  - PDF-Page rendern (bestehende Render-Funktion).
  - Vision-OCR mit Layout-Output (Wörter + BBox) on-demand ausführen.
  - Fuzzy-Match Snippet → Word-Sequence.
  - BBox aggregieren (min/max der Wort-BBoxes).
- Ausgabe: Zitate mit `bbox` ergänzen, Fallback: doc_id+page, wenn kein Match.
- UI: vorhandenes Highlight-Overlay nutzen; bei fehlender BBox nur Seite öffnen.
- Konfig: Timeout + max pages pro Antwort begrenzen.

### Phase 2a Detaillierter Plan (vollständig)
#### Backend – API & Modelle
- Neues Modell `EvidenceRequest`:
  - `citations`: [{ doc_id, page, snippet, source_id? }]
  - `max_pages`: int (default 3)
  - `timeout_seconds`: int (default 30–60)
  - `language`: optional (für Matching-Optimierung)
- Neues Modell `EvidenceMatch`:
  - `doc_id`, `page`, `snippet`, `bbox` (optional), `confidence` (0–1), `status` ("ok" | "no_match" | "error")
- Neuer Endpoint: `POST /chat/resolve-evidence`
  - Nimmt `EvidenceRequest`, liefert Liste `EvidenceMatch`.
  - Wird im Chat-Flow intern nach dem LLM-Aufruf genutzt (kein UI-Call nötig).

#### Backend – Evidence Resolver (Schritte)
1) **Normalize Snippet**: Trim, lower, whitespace collapse, punctuation strip.
2) **Render Page**: PDF-Page rendern (bestehende `render_pdf_pages`).
3) **Layout-OCR On-Demand**:
   - Vision-OCR Prompt erweitern: "Return words with bounding boxes" (strukturierter JSON Output).
   - Ergebnis: Liste von Wörtern mit BBox.
4) **Snippet Matching**:
   - Tokenize snippet + OCR words.
   - Sliding window + fuzzy match (ratio >= 0.8).
   - Fallback: subsequence match (if partial).
5) **BBox Aggregation**:
   - `min(x0,y0)` + `max(x1,y1)` der Wort-BBoxes im Match.
6) **Confidence Score**:
   - aus Match-Score ableiten (e.g., fuzzy ratio).
7) **Return**:
   - `bbox` nur wenn Match ok; sonst status no_match.

#### Backend – Vision OCR Erweiterung
- Neue Funktion `ocr_pdf_pages_with_layout` in `app/services/vision_ocr.py`.
- Prompt-Template für JSON Output:
  - `{ page: int, words: [{text, bbox:[x0,y0,x1,y1]}] }`
- Fallback: wenn Layout-OCR fehlschlägt, return `status=error`.

#### Backend – Performance / Limits
- Max Seiten pro Antwort (`max_pages=3`).
- Hard timeout pro Seite.
- Optional: Cache im RAM für (doc_id, page) → OCR-Layout für 5–10 Min.

#### Backend – Integration in Chat
- Chat-Pipeline:
  1) Retrieve top-k chunks
  2) LLM answer + citations (doc_id/page/snippet)
  3) `resolve_evidence` aufrufen (max 3 Seiten)
  4) Antwort mit bbox-enriched citations zurückgeben

#### Frontend – UI/Viewer
- Keine großen Änderungen nötig: Viewer nutzt bereits bbox.
- Wenn `bbox` fehlt: nur Seite öffnen + Hinweis "keine exakte Fundstelle".
- Optional: Badge "approx." für nicht-exakte Matches.

#### Tests / Validierung
- Unit-Test: Snippet-Match → korrektes BBox aggregiert.
- Integration-Test: 1–2 PDFs mit OCR-Layout, Match → Highlight.

#### MVP-Abnahme
- Frage beantworten → Zitate enthalten bbox bei mind. 1 Seite.
- Fehlende bbox bricht nicht den Chat-Flow.

#### Ausführliche Spezifikation (vollständig)
##### EvidenceRequest Payload
- `citations`: array
  - `doc_id`: int
  - `page`: int (1-based)
  - `snippet`: string (short excerpt from LLM output)
  - `source_id`: optional (index from retrieval)
- `max_pages`: int (default 3, hard max 5)
- `timeout_seconds`: int (default 45)
- `min_match_ratio`: float (default 0.8)

##### EvidenceMatch Payload
- `doc_id`, `page`, `snippet`
- `bbox`: optional `[x0,y0,x1,y1]` in page coordinates (same as existing viewer)
- `confidence`: float (0–1)
- `status`: `"ok" | "no_match" | "error"`
- `error`: optional string

##### OCR Layout Output (on-the-fly)
- Prompt response JSON:
  - `page`: int
  - `words`: [{ `text`: string, `bbox`: [x0,y0,x1,y1] }]
- Normalization rules:
  - Lowercase, collapse whitespace, strip punctuation from both snippet and word tokens.
  - Keep digits and currency symbols.

##### Matching Algorithm (deterministic)
1) Tokenize snippet into words.
2) Tokenize OCR words (already per word).
3) Sliding window across OCR words of length `len(snippet_tokens) ± 2`.
4) Compute fuzzy ratio (e.g., RapidFuzz ratio) on joined strings.
5) Choose max ratio; accept if >= `min_match_ratio`.
6) If no match: fallback to partial token overlap (>=60%).
7) Aggregate bbox of matched word range.

##### Caching
- In-memory LRU:
  - Key: `(doc_id, page, ocr_model)`
  - Value: layout words + bboxes
  - TTL: 5–10 minutes
- Cache size: 50 pages (configurable).

##### Failure / Fallback Behavior
- If OCR fails → return `status=error` (do not break chat).
- If match fails → `status=no_match` (return page-only citation).
- If page render fails → `status=error`.

##### Security / Limits
- Cap `citations` processed to `max_pages`.
- Enforce timeout per page render + OCR call.
- Reject empty snippets or pages <=0.

##### Frontend Integration Details
- Viewer already consumes `{doc_id, page, bbox}`.
- When `status=no_match`, show badge “Seite geöffnet (kein exakter Treffer)”.
- When `status=error`, show badge “Fundstelle nicht ermittelbar”.

##### Implementation Notes
- Add `resolve_evidence` call in chat service only when:
  - citations exist AND
  - at least 1 snippet length >= 20 chars.
- Store original snippet in response for debugging.

## Ausbaustufe: OCR-Qualitäts-Scoring (Prompt-Score)
### Ziel
- OCR-Qualität für Paperless- und Vision-OCR als Kennzahl pro Dokument speichern.
- Separat triggerbarer Task (Queue).

### Datenmodell
- Neue Tabelle `ocr_quality_scores`:
  - `doc_id` (FK)
  - `source` ("paperless_ocr" | "vision_ocr")
  - `score` (int 0–100)
  - `model_name` (string)
  - `method` ("prompt_score")
  - `processed_at` (iso)
- Optional (später): `ocr_quality_pages` für Page-Level-Scoring.

### Backend – Service
- Neuer Service `ocr_quality.py`:
  - Prompt: "Bewerte die OCR-Qualität dieses Texts von 0–100. Gib nur eine Zahl."
  - Pro Seite scoren, pro Dokument aggregieren (Median).
  - Parse robust (erste Zahl im Antworttext).
- Konfig:
  - `OCR_QUALITY_MODEL` (default: TEXT_MODEL)
  - `OCR_QUALITY_MIN_CHARS` (z.B. 50) um leere Seiten zu skippen
  - `OCR_QUALITY_TIMEOUT` (z.B. 30–60s)

### Backend – Queue Task
- Neuer Queue-Task: `ocr_quality`
- Worker-Handler:
  - Lade `DocumentPageText` für `source` (paperless_ocr / vision_ocr)
  - Wenn keine Seiten → skip + status
  - Score berechnen, upsert in `ocr_quality_scores`

### Backend – Endpoints
- `POST /documents/{id}/ocr-quality`:
  - Body: `{ source?: "paperless_ocr"|"vision_ocr", force?: bool }`
  - Enqueue task(s) oder direkt berechnen (optional)
- `POST /documents/ocr-quality`:
  - Body: `{ doc_ids?: [], source?: ..., force?: bool }`
  - Bulk enqueue
- `GET /documents/{id}` erweitert:
  - `ocr_quality`: { paperless: {score, processed_at}, vision: {score, processed_at} }

### UI (später)
- Detailansicht: Anzeige der OCR-Qualität je Quelle.
- Optional: Hinweis "Vision besser" wenn Score +X höher.
- Operations: Button "OCR-Qualität messen" für alle Dokumente.

## Roadmap (short)
- Client refactor: extract logic from `views/*.vue` into composables/stores and shared components.
- Server refactor: consolidate queue/task logic and standardize error handling.

## Recent changes (2026-02-02 to 2026-02-03)
- Backend refactor: centralized `get_settings` dependency for routes in `app/deps.py`.
- Backend refactor: extracted pagination helper shared by meta cache + sync.
- Frontend refactor: unified footer and cleaned up interval cleanup in `App.vue`.
- Frontend refactor: extracted header navigation into `AppNav` component.
- Backend fix: use `get_settings` in embeddings status endpoint (post-refactor).
- Frontend refactor: `AppNav` now receives nav items via props for configurability.
- Backend refactor: shared ETA calculation via `services/time_utils.py`.
- Backend refactor: standardized SyncState lifecycle helpers in `services/sync_state.py`.
- Backend refactor: reduced queue route boilerplate with `queue_disabled_response`.
- Backend refactor: normalized Paperless base URL via `paperless.base_url`.
- Backend refactor: centralized queue task sequences in `services/queue_tasks.py`.
- Backend refactor: consolidated Qdrant collection init in `services/embedding_init.py`.
- Backend refactor: extracted meta upsert helpers for tags/correspondents/document types.
- Backend refactor: unified page-text collection with cached/regenerated vision OCR.
- Backend refactor: consolidated queue-enabled embedding enqueue logic.
- Backend refactor: moved meta page sync into `services/meta_sync.py`.
- Backend refactor: standardized suggestion generation + persistence helpers.
- Backend refactor: extracted queue-based embedding status response helper.
- Backend refactor: centralized LLM base URLs + client in `services/llm_client.py`.
- Backend refactor: centralized Qdrant client helpers and shared guard checks.
- Backend refactor: suggestion store now supports single-commit persistence + reused parsing helpers.
- Backend refactor: worker task dispatch uses a handler map.
- Backend refactor: centralized Qdrant search helper and standardized queue task keys.
- Backend refactor: split documents routes into read/suggestions/actions modules.
- Backend refactor: added document helpers for PDF fetch + document lookup; standardized queue enable guard in routes.
- Backend refactor: consolidated clear intelligence logic and removed redundant enqueue branch.
- Backend refactor: unified enqueue logic for queue tasks.
- Backend tests: added route-level tests for new documents modules.
- Dev: documented .env settings with inline comments.
- Fix: restore missing embed_text import in worker.
- UX: show current document values under AI suggestions with note tooltip icon for summary.
- Backend: store AI summary note in readable format with model/created line and KI-Zusammenfassung footer.
- Backend: allow priority suggest-field variants to run synchronously (skip queue).
- Backend: normalize suggest-field variants response to a list for API validation.
- Frontend: accept list-style suggestion variants from API responses.
- Continue-processing: sync progress modal, enqueue summary toast, batch limit slider.
- Missing-work logic: only enqueue missing items; vision embedding source tracked.
- Operations page: destructive actions + wipe local data + runtime config + copy buttons.
- UX: local overrides shown, badges + tooltips, suggestion metadata surfaced.
- UX: Document list now shows per-task status icons (embeddings, vision OCR, suggestions by source, sync, overrides) with red/amber/green status badges.
- Queue: ETA display, last run timestamp, reset counters when idle.
- Processing: Vision OCR enqueue order prefers shorter documents first (page_count).
- Feature: Added Dashboard page with document stats, tags/correspondents breakdown, and page count distribution.
- Feature: Dashboard extended with monthly processing trend, document types, and unprocessed-by-correspondent charts.
- UX: Dashboard extended section now supports 12/24/all month toggle with larger, report-style charts.
- Branding: Updated app name to “Paperless-NGX Cortex” with slogan “Your documents, understood.”
- DevOps: Added Dockerfile and compose variants for app-only and full stack deployment.
- DevOps: Added worker-only compose variant.
- DevOps: Added worker entrypoint guard for QUEUE_ENABLED and worker env template.
