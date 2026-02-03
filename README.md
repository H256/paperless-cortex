# Paperless-NGX Cortex

## Getting Started

### Prerequisites
- Python 3.13+
- Node.js (for frontend)
- PostgreSQL
- Qdrant (vector database)
- Ollama (for embeddings and vision OCR)
- Redis (optional, for queue-based processing)

### Installation

1. **Backend setup (recommended: uv)**
   ```bash
   cd backend
   uv sync
   ```

2. **Frontend setup**
   ```bash
   cd frontend
   npm install
   ```

3. **Configure environment**
   - Copy `.env.example` to `.env` (repo root)
   - Update with your Paperless-ngx, PostgreSQL, Qdrant, and Ollama settings

4. **Run database migrations**
   ```bash
   cd backend
   uv run alembic upgrade head
   ```

### Running the Application

You need to start three components:

1. **Start the backend API (FastAPI app)**
   ```bash
   cd backend
   uv run uvicorn app.main:app --reload --port 8000
   ```

2. **Start the worker** (optional, for queue-based processing)
   ```bash
   cd backend
   uv run python -m app.worker
   ```
   Note: The worker requires `QUEUE_ENABLED=1` and Redis to be configured in your `.env`.

3. **Start the frontend**
   ```bash
   cd frontend
   npm run dev
   ```

The frontend will be available at `http://localhost:5173`.

## Docker (compose)

### App-only (frontend + backend in one container)
Builds the frontend inside the container and serves it from the backend.
```bash
docker compose -f docker-compose.app.yml up --build
```

### Full stack (includes Postgres, Redis, Qdrant, Ollama)
```bash
docker compose -f docker-compose.full.yml up --build
```

### Worker-only (separate container)
```bash
docker compose -f docker-compose.worker.yml up --build
```

Notes:
- Update `.env` with Paperless + token settings.
- `.env.worker.example` provides a minimal worker-focused template.
- Full stack uses local service URLs for DB/Redis/Qdrant/Ollama; adjust as needed.

## Concise flow
1) **Sync metadata + OCR**  
   The backend pulls document metadata and the Paperless OCR text via API and stores them in Postgres.

2) **Page text layers**  
   - If the Paperless OCR text contains form-feed page breaks, it is split into pages.  
   - Otherwise, the PDF is downloaded and text is extracted per page (pdfminer).  
   - If vision OCR is enabled, pages are rendered to images and sent to Ollama for OCR.  
     On re-processing (`force_embed=true`) all pages go through vision OCR.

3) **Quality scoring**  
   Each page is scored with heuristic metrics (length, alnum ratio, vowel ratio, word-likeness, etc.).  
   Scores are logged and attached to the chunk payload as `quality_score`.

4) **Embeddings (dual-layer)**  
   For every page, chunks are created and embedded for both layers:  
   - baseline text (Paperless OCR / pdfminer extraction)  
   - vision OCR text  
   Each Qdrant point stores `doc_id`, `page`, `source`, and `quality_score`.

5) **Search**  
   `/embeddings/search` returns matches with `doc_id`, `page`, `snippet`, `score`, `combined_score`, `source`, and `quality_score`.
   Search oversamples vector hits, applies a lexical/phrase boost, and reranks before trimming back to `top_k`.

## What's implemented now
- **Backend**
  - Sync Paperless metadata into Postgres (read-only).
  - Page-aware text extraction + quality scoring per page.
  - Vision OCR (Ollama) with per-page rendering, max-dimension scaling, and logging.
  - Embeddings stored in Qdrant with `doc_id`, `page`, `source`, `quality_score`.
  - Suggestions pipeline (two runs: Paperless OCR + Vision OCR) stored in DB with "best pick."
  - Queue-backed processing with Redis + worker and status/ETA.
  - Health/status endpoint and system heartbeat for worker.
- **Frontend**
  - Documents list with filters, sorting, status badges, and Paperless link.
  - Document detail: text quality, page texts, suggestions side-by-side with field variants and apply.
  - Semantic search page with source filter, quality slider, dedupe/rerank.
  - Queue management page.
  - Footer status lights for Web / Worker / Ollama.
  - Generate API client (Orval): `ORVAL_API_URL=http://localhost:8000/api/openapi.json npm run api:generate`

## Key endpoints (backend)
- `POST /api/sync/documents` syncs Paperless -> DB (optional embedding).
- `POST /api/embeddings/ingest` or `/ingest-docs` enqueues/embeds.
- `GET /api/embeddings/search` semantic search.
- `GET /api/documents/{id}/suggestions` (paperless_ocr / vision_ocr / best_pick).
- `POST /api/documents/{id}/suggestions/field` field variants (title/date/correspondent/tags).
- `POST /api/documents/{id}/suggestions/field/apply` store selected variant.
- `GET /api/queue/status`, `POST /api/queue/clear`, `POST /api/queue/reset`.
- `GET /api/status` system status (web/worker/ollama + paperless_base_url).

## Queue + worker
- When `QUEUE_ENABLED=1`, sync/embedding calls enqueue doc IDs to Redis.
- Worker consumes queue and runs full processing: OCR -> embeddings -> suggestions.
- UI shows queue stats and ETA from `/api/embeddings/status`.

## Prompts
- Stored under `backend/app/prompts/`.
- Main suggestions prompt: `suggestions.txt`.
- Field prompts: `suggestions_title.txt`, `suggestions_date.txt`, `suggestions_correspondent.txt`, `suggestions_tags.txt`.
- Vision OCR prompt: `vision_ocr.txt` (or `VISION_OCR_PROMPT`).

## Notes
- Paperless remains the source of truth; no automatic writeback is performed.  
- Vision OCR is optional and controlled by env (`ENABLE_VISION_OCR`, `VISION_MODEL`).  
- Re-process uses full vision OCR to improve handwritten/low-quality pages.
- TLS verification can be disabled for internal certs via `HTTPX_VERIFY_TLS=0`.
