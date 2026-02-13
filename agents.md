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
- UX: improve variant text contrast in dark mode.
- Frontend: prefer direct variants array in suggest-field responses.
- UI: add reusable ConfirmDialog/ChoiceDialog and replace browser confirms.
- Suggestions: generate variants for all fields and add choice dialog for applying variants.
- Suggestions: collapse variant lists and add loading/disable states for variant actions.
- Refactor: split document detail view into metadata, text quality, suggestions, and pages components; restore page preview in pages tab.
- UI: move PDF viewer back to always-visible detail view; pages tab remains for OCR text.
- Pages tab: add jump-to-PDF-page button for OCR entries.
- Pages tab: simplify extracted text layout to single column.
- Suggestions tab: restore layout with best pick full width + paperless/vision two-column row.
- Fix: use bestPickPanel bindings inside suggestions layout.
- Fix: remove stray panel references in best-pick actions.
- Fix: bind props in DocumentPagesSection to avoid runtime undefined access.
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
- Feature: added stored OCR quality scores per source with API endpoint and detail page display; new OCR scoring settings documented in env templates.
- UX: added OCR score explainer block in Text & Quality section.
- Docs: clarified OCR scoring in README.
- Suggestions: best-pick summary now prefers OCR source with better score.
- Suggestions: allow saving summary as note from paperless/vision panels.
- UX: added SSE status stream (queue/worker/sync/embeddings/health) to reduce polling.
- UX: SSE stream now also pushes document stats to avoid stats polling.
- Backend: cache LLM model list in status stream (TTL) to reduce /v1/models calls.
- Docs: added execution blueprint for large-document worker processing in `docs/execution-blueprint-large-doc-worker.md` (page-first ingestion, token budgets, hierarchical summaries, stable suggestions contract).
- Backend: worker now supports page-level notes generation (`page_notes_paperless` / `page_notes_vision`) and hierarchical section/global summaries (`summary_hierarchical`) for large documents.
- Backend: added persistent tables for `document_page_notes` and `document_section_summaries` with dedicated migration.
- Backend: hierarchical section aggregation now uses token-estimate budgets (not only fixed page counts) and suggestions for large docs can use distilled page-note context.
- Tests: added unit coverage for OCR text cleanup and token-budget-based section grouping.
- Tests: stabilized backend test fixture on Windows by using unique temp SQLite files per test run (avoids file-lock collisions).
- Ops: tuned worker/env safe rollout defaults for large-document stability (smaller embedding batches, stricter summary budgets, lower suggestions context cap) and documented Arcane initial profile in the execution blueprint.
- Backend/UX: added triggerable text-cleanup flow (`cleanup_texts` worker task + `/documents/cleanup-texts` endpoint), plus per-document operations endpoints for task enqueue and full reset+sync+reprocess; wired into Maintenance and Document Detail Operations tab.
- UX: removed legacy top-level reprocess controls in document detail; processing actions now live exclusively in the document `Operations` tab.
- Cleanup: text normalization now strips HTML markup from OCR/VLM outputs and flattens HTML tables to plain text (`col1 | col2`) for cleaner embeddings/search/chat input.
- Refactor/Hardening: page-notes extraction now prefers text-template parsing with deterministic fallback for empty/non-JSON model outputs; frontend document operations were de-duplicated via action config + shared operation runner; LLM debug logging now captures input snippets and streamlined debug checks.
- PoC: added safe writeback planning flow (`/writeback/dry-run/preview` + `/writeback/dry-run/execute`) with no Paperless write calls, diff visualization UI (`/writeback-dry-run`), checkbox selection, and logged dry-run call plans for title/date/correspondent/tags/note updates (including AI summary replace/add decision logic).
- Next session focus: hardening pass for writeback queue UX and batch conflict-resolution strategy (doc-level conflict handling, skip/apply rules, clearer progress/error feedback during execute-pending runs).
- Backend: added canonical per-document pipeline endpoints `GET /documents/{id}/pipeline-status` and `POST /documents/{id}/pipeline/continue` with deterministic missing-task planning.
- Backend: refactored `process-missing` internals to reuse shared pipeline cache/evaluation helpers for better DRY/KISS and consistent task detection.
- Frontend: wired document detail operations to canonical pipeline endpoints (status + continue), replaced local heuristic status cards with backend-driven step states, and added a single-click "Continue missing processing" action.
- Backend: set canonical pipeline defaults to include large-document steps (`page_notes` + `summary_hierarchical`) so status and default continue/reprocess runs no longer miss large-doc processing.
- UX/Processing: refined "Continue processing" modal with explicit embedding mode (`auto`/`vision`/`paperless`), embedding-enable derivation from source checkboxes, and clearer embeddings status wording; API response model now declares `selected` for process-missing consistency.
- Frontend architecture: added Vue Query (`@tanstack/vue-query`) plugin setup, introduced `useDocumentPipeline` composable for pipeline status/continue calls, and removed pipeline-specific state/actions from `documentDetailStore` to keep the store lean.
- Frontend architecture: extracted document continue-processing preview/start/cancel flow into `useContinueProcessing` (Vue Query mutations), updated `DocumentsView` to use composable state directly, and removed obsolete process-preview/cancel logic from `documentsStore`.
- UX hardening: added explicit error handling/toasts around continue-preview/start/cancel actions in `DocumentsView` and made preview-refresh watchers resilient to transient request failures.
- Frontend typing: generalized Orval response unwrapping in `src/api/orval.ts` to correctly handle generated success/error unions; this removed the large service-layer type-check error block and reduced remaining issues to view/component-level typings.
- Frontend typing/hardening: resolved remaining view/component type issues (`DocumentSuggestionsSection`, `PdfViewer`, `DocumentDetailView`, `DashboardView`, `QueueView`) including nullable IDs, bbox tuple typing, safer suggestion-tag parsing, and pdf.js render params; `npm run type-check` now passes.
- Frontend architecture: introduced `useDocumentsCatalog` (Vue Query) for document list + meta retrieval/filter state in `DocumentsView`, removed list/meta fetch responsibilities from `documentsStore`, and kept sync/status state centralized in store; frontend type-check remains green.
- Frontend architecture: migrated `DashboardView` to a Vue Query-backed `useDashboardData` composable and `QueueView` to a Vue Query-backed `useQueueManager` composable (status/running/peek + mutations), then reduced `queueStore` to shared status + clear/refresh responsibilities used by app-wide status/SSE flows.
- Frontend architecture: added `useMaintenanceOps` (Vue Query) to centralize maintenance-page processing/runtime/worker-lock queries and destructive operation mutations (reprocess, cleanup, clear, delete vision/suggestions/embeddings, sync tags/correspondents).
- Frontend refactor: migrated `MaintenanceView` from `documentsStore` + direct service calls to `useMaintenanceOps`, removing manual loading flags in favor of mutation/query pending state and adding explicit error toasts for tag/correspondent sync + reprocess start failures.
- Frontend cleanup: removed maintenance-only actions (`reprocessAll`, remove/delete/clear helpers) from `documentsStore`, keeping it focused on shared sync/embed/stats state consumed by app-level SSE/status flows.
- Frontend architecture: added `useDocumentOperations` composable for document-level operations-tab mutations (enqueue task, cleanup texts, reset+reprocess) with shared queue/pipeline query invalidation.
- Frontend refactor: removed direct document-operations service calls from `DocumentDetailView` and wired operations through `useDocumentOperations`, leaving the view focused on orchestration/UI messages while preserving existing queue/pipeline refresh behavior.
- Frontend architecture: added `useProcessingOverview` (Vue Query) for sync/embed/stats/queue status plus cancel+clear orchestration; `DocumentsView` now consumes this composable and no longer depends on `documentsStore`/`queueStore` status refs.
- Frontend architecture: removed now-obsolete `documentsStore` and switched `App.vue` SSE fan-out to update Vue Query caches directly (`sync-status`, `embed-status`, `documents-stats`, `queue-status`) while keeping footer queue store updates for global status display.
- Frontend architecture: removed `queueStore`; `App.vue` now reads footer queue status from Vue Query (`queue-status`) and updates that cache directly from SSE, while `DocumentDetailView` operation orchestration no longer depends on queue store refresh calls.
- Backend robustness: added embedding input budget guard (`EMBEDDING_MAX_INPUT_TOKENS`) and deterministic chunk normalization before worker embedding calls (`enforce_embedding_chunk_budget`), plus overflow fallback split+average in `embed_text` for provider-side context overrun errors.
- Backend quality: hardened `semantic_chunks` against single oversized sentence fragments, added focused tests in `backend/tests/test_embedding_chunk_budget.py`, and documented new env tuning in `.env.example`, `.env.worker.example`, and `docs/execution-blueprint-large-doc-worker.md`.
- Frontend architecture: removed `documentDetailStore` and introduced `useDocumentDetailData` composable (Vue Query mutations + local refs) to centralize document detail data loading/actions without Pinia store indirection.
- Frontend refactor: `DocumentDetailView` now consumes `useDocumentDetailData` directly (document/meta/page-text/quality/OCR/suggestions + variant/application flows), with explicit per-doc loader wrappers for readability and reduced cross-layer coupling.
- Frontend architecture: added `usePaperlessBaseUrl` composable backed by Vue Query runtime status (`runtime-status`) and migrated `DocumentsView`, `DocumentDetailView`, and `SearchView` to it, removing direct `statusStore` dependency for Paperless URL link rendering.
- App SSE integration: `App.vue` now updates the `runtime-status` query cache on status stream events so shared runtime URL consumers stay in sync without view-level store coupling.
- UX/Frontend refactor: extracted the large continue-processing preview modal from `DocumentsView` into reusable component `frontend/src/components/ContinueProcessingModal.vue`, reducing `DocumentsView` template noise while preserving existing behavior/options and start/close flow.
- Frontend refactor: extracted processing ETA/progress/queue metric derivations from `DocumentsView` into `frontend/src/composables/useProcessingMetrics.ts`, reducing duplicated time/rate math in the view and keeping state orchestration focused.
- Frontend refactor: extracted continue-processing option state and API payload mapping (batch slider + checkbox set) into `frontend/src/composables/useContinueProcessOptions.ts`, further slimming `DocumentsView` orchestration code.
- Frontend architecture: split document detail data responsibilities into dedicated composables: `useDocumentDetailCoreData` (document/meta/page-text/quality/OCR) and `useDocumentSuggestions` (suggestions/variants/apply flows), with `useDocumentDetailData` retained as a thin composition wrapper for stable view integration.
- UX/Frontend refactor: extracted document row processing-status icon rendering from `DocumentsView` into reusable component `frontend/src/components/DocumentProcessingBadges.vue`, removing view-local icon ordering/count/tooltip helpers and improving `DocumentsView` readability.
- UX/Frontend refactor: extracted documents filter controls block from `DocumentsView` into `frontend/src/components/DocumentsFiltersPanel.vue` with explicit v-model bindings and reload emit, reducing template size and keeping filter UI concerns isolated.
- UX/Frontend refactor: extracted documents list table + pagination from `DocumentsView` into `frontend/src/components/DocumentsTable.vue` (including sort header controls and row actions), leaving the view focused on state orchestration and handlers.
- Frontend refactor: extracted visible-documents filtering (analysis/model filter derivation) into `frontend/src/composables/useVisibleDocuments.ts` and removed now-unused date-format helper leftovers from `DocumentsView` for a leaner view script.
- Frontend refactor: extracted continue-processing action handlers (`openPreview`, `startFromPreview`, `cancelProcessing`, post-action refresh orchestration) from `DocumentsView` into `frontend/src/composables/useDocumentsProcessingActions.ts`, reducing view-side async workflow noise.
- Frontend refactor: extracted documents table control handlers (`toggleSort`, `prev/next page + reload`) from `DocumentsView` into `frontend/src/composables/useDocumentsTableControls.ts` to keep pagination/sort behavior isolated and reusable.
- Frontend refactor: extracted continue-preview auto-refresh watchers (options/batch change handling) from `DocumentsView` into `frontend/src/composables/usePreviewAutoRefresh.ts`, reducing reactive boilerplate in the view while preserving refresh-on-change behavior.
- UX/Frontend refactor: extracted documents processing action bar (continue/cancel processing controls) from `DocumentsView` into `frontend/src/components/DocumentsProcessingToolbar.vue`, further reducing view template noise and improving component composition.
- UX/Frontend refactor: extracted documents overview header panel (stats grid + active processing status block) from `DocumentsView` into `frontend/src/components/DocumentsOverviewPanel.vue`, further isolating presentation concerns from orchestration logic.
- Frontend architecture: extracted App-level SSE stream lifecycle and query-cache fan-out into `frontend/src/composables/useStatusStream.ts`; `App.vue` now delegates status stream start/stop and keeps only shell-level wiring.
- Frontend cleanup: extracted writeback conflict presentation helpers (`conflictFieldLabel`, `conflictValue`) from `DocumentDetailView` into shared utility `frontend/src/utils/writebackConflict.ts` to reduce in-view helper noise and improve reuse potential.
- Writeback UX/Backend hardening: extended `POST /writeback/jobs/execute-pending` response with per-job result details (`status`, `error`, doc/call counts), then updated `WritebackDryRunView` Queue tab to show a "Last bulk run details" table so failed execute-pending runs expose actionable errors immediately.
- Frontend refactor: extracted writeback preview rendering helpers (`rows`, field labels, value formatting) from `WritebackDryRunView` into `frontend/src/utils/writebackPreview.ts` to reduce view script noise and keep formatting logic reusable/testable.
- Processing pipeline: added `include_sync` support to continue-processing endpoints and UI options so "Continue processing" can sync first in the same run; per-document pipeline status/continue now includes sync task planning when local doc is stale.
- Embeddings pipeline: introduced source-aware Qdrant point IDs/deletion (`paperless` vs `vision`) so both embedding sources can coexist, plus `embeddings_mode=both` planning support for process-missing and pipeline-continue flows.
- API/frontend alignment: regenerated OpenAPI/Orval client (including writeback + pipeline contracts), switched `frontend/src/services/writeback.ts` to generated client wrappers, and introduced Vue Query composable `frontend/src/composables/useWritebackManager.ts` for writeback preview/jobs/history/mutations in `WritebackDryRunView`.
- Next hardening track (in progress): improve UX smoothness and worker robustness with (1) structured JSON logging + error taxonomy, (2) persistent task-run events for queue/worker observability, (3) backend/API + UI log inspector for per-doc/per-task troubleshooting, and (4) retry/dead-letter style handling for transient failures.
- Observability phase 1: added configurable structured logging (`LOG_JSON`, `LOG_LEVEL`) with shared formatter/setup (`app/services/logging_setup.py`) and worker error taxonomy (`app/services/error_types.py`) to emit concrete `error_type` values for task failures.
- Observability phase 1: introduced persistent `task_runs` tracking (`TaskRun` model + Alembic migration `c9d3a7f1b214` + `app/services/task_runs.py`) and wired worker execution lifecycle to create/finish per-task run records with status, duration, worker id, and typed errors.
- Observability phase 1: added queue inspector endpoint `GET /queue/task-runs` with filtering (`doc_id`, `task`, `status`, `error_type`, pagination), plus backend route tests in `backend/tests/test_queue_task_runs_routes.py`.
- Observability phase 1 UI/API: regenerated OpenAPI/Orval client for new queue task-runs contracts and wired Queue Manager to show filterable recent task-run history (doc/task/status/error type, duration, start time) via Vue Query (`useQueueManager`) and generated endpoint bindings in `frontend/src/services/queue.ts`.
- Worker robustness phase 1: added bounded automatic retries for retryable worker errors (`WORKER_MAX_RETRIES`, retry_count payload propagation), persisted attempt numbers in `task_runs`, and recorded retry state (`retrying`) with typed error metadata.
- Config/docs/tests: documented logging/retry env vars in `.env.example` and `.env.worker.example`, and added unit coverage for error classification/retryability in `backend/tests/test_worker_error_types.py`.
- Worker robustness phase 2: implemented delayed retry backoff queue handling (`enqueue_task_delayed`, `move_due_delayed_tasks`) plus Dead-Letter Queue support (`/queue/dlq`, `/queue/dlq/requeue`, `/queue/dlq/clear`) for tasks that still fail after retries.
- Worker checkpoints: added `checkpoint_json` to `task_runs` and periodic checkpoint updates for long-running stages (vision OCR batches, embedding chunk batches, page notes, section summaries) so progress can be inspected while running.
- UX/Observability: added Queue Manager Dead-Letter Queue panel (reload/clear/requeue) and per-document processing timeline in `DocumentDetailView` operations tab using filtered `task_runs` (status/attempt/checkpoint/error visibility).
- Worker checkpoints phase 2: retries now attach a `resume_from` marker based on the latest persisted checkpoint for the same doc/task source; Queue history can distinguish resumed attempts from fresh runs.
- Worker robustness phase 2: tightened progress granularity for very large runs by reducing vision OCR and embedding batch sizes adaptively, improving checkpoint frequency and lowering rework scope after failures.
- Queue UX: task-run history now includes a checkpoint column and a compact `resume` badge for runs that restart from a previous checkpoint marker.
- Worker resume semantics phase 3: retry runs now actually resume long stages from checkpoint where safe (vision OCR page offset, embedding chunk offset without deleting prior points, page-notes page offset). Hierarchical section summaries resume only when persisted section rows prove consistency; otherwise stage restarts from section 0 to avoid partial-loss corruption.
- Tests: added checkpoint resume-selection coverage in `backend/tests/test_worker_resume_checkpoint.py`.
- Queue observability UX: added delayed-retry queue visibility (`GET /queue/delayed`) with due timestamps/remaining backoff, surfaced in Queue Manager as a dedicated "Delayed retries" panel.
- Continue-processing UX: added a compact pipeline-coverage checklist in `ContinueProcessingModal` (paperless baseline, vision pipeline, large-doc extras, overall docs with gaps) to make missing scope clearer before enqueue.
- Document detail UX: operations status now explicitly indicates whether large-document mode is active and clarifies that page notes + hierarchical summary are required when applicable.
- Documents UX: added live per-document running-progress indicators in the list table, derived from running task checkpoints (`queue/task-runs?status=running`) to show active stage progress (`Vision OCR 12/37`, `Embeddings 40/120`, etc.).
- Document detail UX: processing timeline now offers a one-click retry action for failed task runs, re-enqueuing the same task/source with dedupe-aware feedback.
- Hotfix: `/queue/task-runs` now safely parses malformed legacy `checkpoint_json` values (returns `checkpoint=null` instead of 500), preventing frontend "Unexpected token 'I'" errors in Processing timeline reload.
- Hotfix: task-run service calls now degrade gracefully when `task_runs` table is missing (return empty list / skip bookkeeping) to prevent hard 500s before migrations are applied.
- Continue-processing UX: `process-missing` now returns lightweight preview details (`missing_by_step` + `preview_docs` with missing task list), and the modal shows a concrete sample list of affected documents for faster triage before enqueue.
- Queue UX: added bulk action "Retry failed (filtered)" in task-run history, deduping by doc/task/source and re-enqueuing supported per-document tasks through existing operations endpoint.
- Sync hardening: replaced `Document.notes` clear+reinsert with idempotent merge-by-note-id in `_upsert_document`, preventing duplicate PK collisions (`document_notes_pkey`) during repeated sync/continue runs.
- Worker resilience: added explicit DB rollback before task-run bookkeeping after task execution failures and ensured running-task marker is cleared on worker shutdown, preventing pending-rollback cascades and stale "running" UI state after exceptions/interrupts.
- Tests: added `backend/tests/test_sync_upsert_notes.py` to verify note upsert idempotency with stable note IDs.
- Queue robustness: hardened running-state handling by clamping `in_progress` decrement at zero and auto-clearing stale running markers when lock/heartbeat are absent, reducing orphaned "running" UI states after crashes/interrupted workers.
- Continue-processing UX simplification: replaced checkbox-heavy source/task toggles with a single guided strategy selector (`balanced`, `vision_first`, `paperless_only`, `max_coverage`) in `useContinueProcessOptions` + `ContinueProcessingModal`, while preserving backend-compatible query payload mapping.
- Documents list UX: added writeback/readiness status pills in `DocumentProcessingBadges` (`Needs review`, `Reviewed`, `Local overrides`) to make local-only vs review/writeback state visible directly in table rows.
- Critical sync fix: resolved persistent `document_notes_pkey` collisions by handling global note-id clashes during sync upsert (legacy positive local notes are re-keyed into negative local-id space before remote note insert/update), with explicit flush to avoid identity-map conflicts.
- Local note id policy: AI/local-only notes now allocate negative IDs in both suggestion apply flow and writeback local-sync note flow, preventing future collisions with Paperless positive note IDs.
- Follow-up critical fix: resolved remaining cross-document note-ID collisions in sync by checking global `DocumentNote` identity (`db.get`) and re-keying conflicting existing rows before applying remote note IDs; added flush after re-key to prevent identity-map conflicts in the same transaction.
- Added regression coverage for legacy positive local note collision vs incoming remote note ID in `test_upsert_document_notes_remaps_legacy_positive_collision`.
- Continue-processing UX feedback: added explicit kickoff loading state (`Starting...`) in `DocumentsProcessingToolbar` plus inline kickoff banner in `DocumentsView` while enqueue/start is pending, so users see immediate activity after pressing continue.
- Queue/detail timeline UX: standardized relative task-run start timestamps ("15m ago") with shared formatter utility (`frontend/src/utils/dateTime.ts`) and kept absolute datetime in hover tooltips, reducing repeated view-local date/time helpers.
- Queue/detail timeline UX: added shared `useAutoRefresh` polling composable and wired Queue Manager + Document Detail timeline to auto-refresh while work is active/running, so users see live progress without manual reload clicks.
- Document detail UX: added a header-level live "Processing now" badge (task + checkpoint stage/progress) based on active task-run state to make ongoing background work immediately visible.
- Backend robustness: hardened task-run service methods against stale failed SQLAlchemy session state (`PendingRollbackError`) by normalizing session readiness before bookkeeping/list queries; added regression tests proving `finish_task_run` and `list_task_runs` recover after prior failed transactions.
- Frontend DRY: extracted shared checkpoint formatting/resume-marker helpers into `frontend/src/utils/taskRunCheckpoint.ts` and reused them in Queue view, Document detail timeline, and running-progress composable to remove duplicated checkpoint parsing logic.
- Backend refactor: cleaned `task_runs` service with shared recovery/query helpers (`_run_with_pending_recovery`, `_build_task_runs_query`) to reduce duplicate branches and keep pending-rollback handling consistent across create/finish/checkpoint/list/find paths.
- Queue UX observability: Queue Manager now shows live refresh state (`active`/`idle`) and last refresh timestamps (relative + absolute), making background polling visibility explicit when processing is ongoing.
- Backend/API: added document fan-out endpoint `GET /documents/{id}/pipeline-fanout` to expose ordered downstream processing chain (sync/vision/embeddings/page-notes/summary/suggestions) with per-step state derived from missing-work evaluation + latest task-run status/checkpoint.
- Document detail UX: added "Downstream fan-out" panel in Operations tab with ordered task chain, live statuses, last-run timestamps, and checkpoint snippets; fan-out auto-refreshes alongside pipeline/timeline while work is running.
- Queue log explorer hardening: extended `GET /queue/task-runs` with free-text filter `q` (task/source/status/error-type/error-message) and updated Queue Manager filters/table to search and display compact error messages for faster troubleshooting.
- Worker telemetry: embedding pipeline now records chunk-split and overflow-fallback counters into task checkpoints (`split_chunks`, `split_parts`, `overflow_fallback_calls`, `overflow_fallback_parts`), and document timeline surfaces this telemetry for embedding runs.
- API/client: regenerated OpenAPI/Orval client for new fan-out endpoint and queue task-run `q` filter; document/queue composables now consume generated contracts.
- Tests: added coverage for queue task-run text-query filtering, document pipeline fan-out endpoint response, embedding split telemetry summary, and overflow-fallback telemetry tracking.
- Document timeline UX: enhanced per-document processing timeline with inline filters (`status`, free-text `q`) and compact error-message previews; implemented via extended `useDocumentTaskRuns` composable filters to keep timeline inspection DRY and reusable.
- Queue run-history UX: made rows actionable by adding direct jump-to-document buttons and one-click copy for raw error messages, reducing context switching during failure triage.
- UX/Observability: added dedicated Log Inspector page (`/logs`) with advanced task-run filtering (doc/task/status/error/query), auto-refresh toggle, saved filter presets (localStorage), direct jump-to-document actions, and error copy support for faster end-to-end troubleshooting.
- Frontend architecture: introduced reusable `useTaskRunInspector` composable to keep log-query/filter/preset state isolated and DRY; wired app navigation with new Logs entry.
- Log Inspector UX: added server-side pagination controls via `offset` (`Prev`/`Next`), quick filter chips (`Only failed`, `Retrying now`, `Embedding overflows`), and export actions for currently filtered rows (`JSON`, `CSV`).
- Hierarchical summary robustness: fixed section-summary JSON parsing failures by adding truncated-JSON repair in `_extract_json_dict`, a compact retry prompt for section aggregation, and deterministic fallback section-summary synthesis when model output remains non-JSON; this prevents complete section-summary dropouts on large/verbose model outputs.
- Tests: extended `test_hierarchical_summary_parsing.py` with truncated-JSON repair, deterministic section fallback, and `generate_section_summary` fallback-path coverage.
- Hierarchical summary robustness (follow-up): reduced section prompt bloat via deterministic page-note compaction (`facts/entities/references/key_numbers` caps per page + token-budgeted page inclusion), improved JSON extraction to decode the first valid object even with trailing noise, and added parsing/compaction regression tests.
- Page-notes guardrail hardening: added model-output sanitization for control/meta tokens (e.g. `<|channel|>...`), prompt-echo/meta detection, strict retry prompt for contaminated page-note responses, and section-compaction sanitization so leaked meta content is not persisted or forwarded into section summaries.
- Document operations UX follow-up: improved per-document "Continue missing processing" feedback by adding explicit enqueue/pickup status banner ("checking", "waiting for worker pickup", "picked up") plus temporary auto-refresh while waiting; also updated document-list running badges to include `retrying` task-runs so active retry progress is visible.
- Document timeline UX follow-up: added one-click "Copy error" action per task-run row in document Operations timeline, mirroring queue troubleshooting flows and reducing context switching during failure triage.
- Continue-processing modal UX pass: added explicit "What Happens Next" execution plan, live runtime-state block (queue enabled/length + worker activity), stronger post-enqueue success message, and clearer primary action wording ("Start processing (enqueue)") so enqueue vs worker execution is unambiguous.
- Hierarchical summary quality fix: global summary generation now mirrors section-summary hardening (primary JSON parse -> compact retry -> deterministic fallback synthesis from section summaries), and suggestion context builder now ignores error-only/empty `hier_summary` payloads so large-doc suggestions fall back to useful page-note context instead of "global_summary_error" text.
- Continue modal scanability pass: reduced visual noise by removing always-visible low-level missing counters from the top section and moving them into a toggleable "Detailed Missing Counters" panel, keeping default focus on docs/needs-work + coverage.
- Continue modal detail behavior: "Detailed Missing Counters" now auto-expands only when critical missing counts exceed a threshold (currently 10), while preserving manual toggle control during the open session.
- Continue-processing flow polish: after enqueue start, the preview modal now remains open in its success state (instead of closing immediately), so users can confirm enqueued docs/tasks and runtime context before closing manually.
- Continue modal prioritization pass: sample preview docs are now ranked/highlighted by critical-gap priority (large-doc extras + vision downstream tasks), and strategy-specific risk warnings are shown when selected strategy is likely to leave relevant gaps unresolved.
- Continue modal actionability pass: preview doc rows are now directly clickable (open document detail), and detailed counters gained an "only non-zero" filter to reduce low-value noise during troubleshooting.
- Continue modal decision assist: added computed strategy recommendation based on current missing-work profile (vision/paperless/large-doc gaps) with one-click "Use recommended" action to reduce manual strategy guesswork.
- Continue modal readiness pass: added explicit enqueue readiness/status line ("Ready to enqueue" vs reason), expected enqueue docs/tasks summary based on selected batch limit, and disabled start action when no missing work would be enqueued.
- Continue modal scope clarity: added an explicit execution-scope matrix (included/excluded) for sync, paperless baseline tasks, vision tasks, large-doc extras, and dual-embedding coverage based on selected strategy/options.
- Continue modal monitoring shortcut: post-enqueue success panel now provides direct actions to open Queue and Logs views, reducing navigation friction when moving from planning to live monitoring.
- Continue modal layout fix: increased modal max width and added internal vertical scrolling (`max-h` + `overflow-y-auto`) so full content remains usable on smaller screens.
- Continue processing UI extraction: split monolithic modal into reusable `ContinueProcessingPanel` (all controls/content) plus thin `ContinueProcessingModal` wrapper (overlay/open state). This enables straightforward reuse on a dedicated route/page without duplicating logic.
- Section summary sanitization hardening: normalized section-summary payloads (primary/compact/fallback) now strip control/meta/prompt-echo content (including `<|channel|>...`, "we need to extract...", "given OCR text..."), so contaminated reasoning text no longer propagates into persisted section summaries and downstream suggestions.
- Debug observability tweak: added optional full-response LLM logging via `LLM_DEBUG_FULL_RESPONSE=1` (used with `LLM_DEBUG=1`) so model outputs are logged untruncated for JSON/debug investigations.
- Hierarchical pipeline refactor (text-first): page notes, section summaries, and global summary generation now rely on plain-text model outputs (no JSON parsing dependency in these stages). Structured JSON extraction remains primarily in suggestion generation; hierarchy stages store/propagate sanitized text-first payloads for robustness across model changes.
- DB naming alignment: renamed hierarchy storage columns via Alembic migration (`document_page_notes.notes_json` -> `notes_text`, `document_section_summaries.summary_json` -> `summary_text`) and updated backend model/runtime references accordingly.
- Hierarchy persistence cleanup: `notes_text` and `summary_text` now persist actual plain text (not JSON-serialized dict strings); worker summary stage consumes these text fields directly and keeps resume compatibility by reconstructing minimal in-memory payloads.
- Language preservation hardening: page-notes and hierarchical section/global summary prompts now explicitly require preserving source document language(s) (no translation to English), including multilingual documents.

## TODO / Known Issues
- Monitor live worker logs for residual overflow edge cases after budget guard rollout (example doc `1491` scenario addressed by pre-embed split + runtime overflow fallback).
- Validate full end-to-end continue-processing runs on large documents (pickup visibility in `/queue` and troubleshooting in `/logs`) after latest UX flow move to `/processing/continue`.
- UX follow-up: consider adding compact mobile defaults and sticky quick filters for high-throughput unreviewed triage sessions.

## Session Handoff (2026-02-12)
- Branch in progress: `refactor/pipeline-status-and-continue`
- Frontend status:
  - Continue-processing flow is now page-based at `/processing/continue` (no modal).
  - Continue-processing panel is full-width and uses page scroll (no internal overflow scroll).
  - Top nav uses persistent `More` behavior on all screen sizes.
  - Main nav order: Dashboard, Documents, Search, Writeback.
  - `More` order: Chat, Queue, Logs, Operations.
  - `More` closes on blur/focus-out.
- Hierarchical pipeline status:
  - Text-first persistence is active (`notes_text`, `summary_text`), no JSON-first dependency in page/section/global summary stages.
  - Prompting now enforces source-language preservation (no forced English).
  - Sanitization guards strip leaked control/meta reasoning tokens from persisted hierarchy outputs.
- Worker/robustness status:
  - Embedding overflow guard + fallback split logic implemented (`EMBEDDING_MAX_INPUT_TOKENS`).
  - Task-run observability + retry/checkpoint infrastructure active; queue/log inspector flows are in place.
- Docs/config audit:
  - `.env.example` and `.env.worker.example` include comments for recent runtime controls (`LOG_LEVEL`, `LOG_JSON`, `WORKER_MAX_RETRIES`, `EMBEDDING_MAX_INPUT_TOKENS`, `LLM_DEBUG_FULL_RESPONSE`).
  - README updated with latest UX flow notes (continue-processing page, logs page, nav simplification).
- Recommended first checks tomorrow:
  1. Run a full end-to-end continue-processing trial on a large doc and verify downstream pickup visibility in `/queue` and `/logs`.
  2. Re-run hierarchical pipeline on test docs and spot-check language consistency in `document_page_notes.notes_text` and `document_section_summaries.summary_text`.
  3. Decide whether to keep or remove older duplicated historical bullets in this log (non-functional cleanup).
- Writeback sync-state fix: after successful real writeback execution, reviewed timestamp now uses Paperless modified, and local Document.modified is updated from Paperless per affected doc. This prevents false stale/unsynced detection and unnecessary reprocessing in continue-missing flows; covered by new route test for /writeback/execute-now.
- UX slice implementation: added route-query persistence for DocumentsView list state (filters/sort/page/review/model/date) via useDocumentsRouteState, so back-navigation from detail keeps triage context; improved document table mobile responsiveness with horizontal overflow support + min width + stacked pager controls; and reflowed top overview/status layout to prevent sync/queue overlap on small screens.
- UX slice implementation (follow-up): added explicit return-context navigation from documents list to detail via `return_to` query and a header Back button in detail view, plus a user-selectable Documents list `Table/Cards` mode persisted in URL query (`view=cards`).
- UX slice implementation (mobile triage): Documents view now defaults to cards mode on small screens when no explicit iew query is set, and adds a sticky quick-filter bar for review-state triage (unreviewed / 
eeds_review / eviewed / ll) with one-click reset.
- Frontend refactor pass (DRY/KISS): extracted reusable `DocumentsQuickControls` wiring cleanup in `DocumentsView`, removed dead kickoff state from list toolbar usage, hardened query-sync comparison in `useDocumentsRouteState` (key/value equality instead of JSON stringify), and fixed cards subtitle separator rendering in `DocumentsTable`.
- Pipeline staleness fix: document pipeline status/continue no longer invalidates vision OCR, embeddings, page-notes/hier-summary, or suggestions solely because `Document.modified` changed (e.g. metadata-only writeback). Missing tasks now reflect missing/incomplete artifacts and dependency freshness (e.g. notes vs. vision updates), preventing false reprocessing chains after successful writeback.
- Tests: added regression `test_pipeline_status_ignores_metadata_only_modified_for_processing` in `backend/tests/test_documents_routes.py`.
- Writeback UX correctness fix: `/documents/{id}/local` now treats local AI summary note differences (compared to Paperless note markers) as local overrides, so `review_status` becomes `needs_review` and detail-page writeback enablement is correct for note-only changes.
- Tests: added regression `test_get_local_document_note_override_sets_needs_review` in `backend/tests/test_documents_routes.py`.
- Continue-processing UX compact mode: moved high-detail diagnostics (coverage matrix, detailed missing counters, sample-gap docs, execution-scope matrix, runtime block) behind a single `Show diagnostics` toggle in `ContinueProcessingPanel`, keeping core actions/options visible by default for faster scanning.
- Documents triage UX slice: upgraded sticky quick-controls into a single triage action bar with direct shortcuts to `Writeback queue` (`/writeback`) and `Continue processing` (`/processing/continue`), improving mobile/high-throughput review flows without leaving the list context.
- Document-detail writeback UX hardening: writeback button availability now considers real local writeback state (`local_overrides`) in addition to `review_status`, and button label/tooltip now explicitly explain `writing`, `ready`, or `no local changes` states.
- Documents sticky triage bar mobile pass: refactored `DocumentsQuickControls` into clearer sections (header/reset, horizontally scrollable review chips, action row with writeback/continue + view toggle) to reduce wrap clutter and keep controls usable on small screens.
- Mobile triage speed-up slice: document cards now expose direct per-item actions (`Open`, `Continue`) where `Continue` deep-links to detail `Operations` tab; detail view now syncs selected tab with `?tab=` query to support shareable/deeplinked task-focused navigation.
- Document-detail mobile polish: top action bar now wraps responsively (`w-full` on small screens), action button typography scales (`text-xs` -> `sm:text-sm`), and tab navigation switched to horizontal-scroll chips (no cramped multi-row wraps). Also shortened ready-state writeback button text to `Write back` for tighter header fit.
