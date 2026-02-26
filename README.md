# Paperless-NGX Cortex

Paperless-NGX Cortex is a separate intelligence layer for Paperless-ngx. It keeps Paperless as the source of truth, processes documents locally (sync, OCR layers, embeddings, suggestions), and supports explicit manual writeback only.

## What this project is (and why it exists)
I built this because Paperless-ngx is excellent at storage and search, but I wanted a focused intelligence layer that can be audited, resumed, and controlled without ever auto-writing back. The goal is to make document understanding and metadata suggestions fast, local, and reviewable.

## Benefits
- Keeps Paperless-ngx as the source of truth and never auto-writes.
- Adds local OCR quality checks and optional vision OCR without overwriting the baseline.
- Produces embeddings, semantic search, suggestions, and summaries you can review before applying.
- Handles large documents with resumable, observable pipeline steps.
- Surfaces similar documents and potential duplicates from embeddings.

## Processing diagram
```mermaid
flowchart TD
  A[Paperless-ngx] --> B[Sync metadata + baseline text]
  B --> C{Need extra OCR?}
  C -- No --> E[Embeddings]
  C -- Yes --> D[Vision OCR (optional)]
  D --> E
  E --> F[Suggestions]
  F --> G{Large doc?}
  G -- Yes --> H[Page notes + hierarchical summary]
  G -- No --> I[Review]
  H --> I
  I --> J[Manual writeback]
```

## Current status
### Delivery phases
- `MVP` (core intelligence layer): **Done**
  - Sync from Paperless, local storage, embeddings, semantic search, suggestions, queue/worker, manual writeback.
- `Phase 1` (robustness + UX streamlining): **Done**
  - Pipeline hardening + triage/log observability baseline delivered.
- `Phase 2` (advanced evidence locator / on-the-fly bbox resolution): **Planned / partial design only**
  - Spec exists, full implementation not complete yet.

### Practical interpretation
- You can use the app end-to-end today.
- Current engineering focus is quality and reliability, not greenfield features.

## Product principles
- No automatic writeback to Paperless.
- All AI outputs are reviewed locally first.
- Writeback is explicit and manual.
- Local processing should be resumable, observable, and robust for large docs.

## Core flow (current)
1. Sync metadata + text baseline from Paperless.
2. Optionally run vision OCR as additional layer (never overwrite baseline).
3. Generate embeddings (paperless and/or vision source strategy).
4. Generate suggestions (paperless/vision + best pick).
5. For large docs: page notes + hierarchical summary.
6. Review locally, then explicitly write back selected fields.

## Requirements and installation
### Prerequisites
- Python `>=3.13` for the backend.
- Node.js `>=18` for the frontend.
- Paperless-ngx instance reachable by URL and API token.
- Postgres, Redis, and Qdrant (local installs or Docker).
- An OpenAI-compatible LLM endpoint (local or remote).
See `MANUAL.md` for more detailed setup and operations.

### Backend (recommended: uv)
```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

### Backend (pip + requirements.txt)
A pinned `requirements.txt` is generated at `backend/requirements.txt`.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

To refresh `requirements.txt` from `pyproject.toml`:
```bash
cd backend
uv export --format requirements.txt --no-dev --output-file requirements.txt
```

### Worker (optional, queue mode)
```bash
cd backend
uv run python -m app.worker
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Local setup (database + migrations)
1. Copy `.env.example` to `.env` and fill values. Do not commit `.env` to GitHub.
2. Ensure Postgres, Redis, and Qdrant are running.
3. Create the database specified by `DATABASE_URL`.
4. Run migrations with Alembic.

Example Postgres setup:
```bash
createdb paperless_intelligence
createuser paperless
```

Example migrations:
```bash
cd backend
uv run alembic upgrade head
```

## Docker
### App-only (backend + frontend + redis)
```bash
docker compose -f docker-compose.app.yml up --build
```

### Full stack (app + postgres + redis + qdrant)
```bash
docker compose -f docker-compose.full.yml up --build
```
**Important:** `LLM_BASE_URL` must be set in your `.env`. It is not set in `docker-compose.full.yml`.
Docker uses `:8000` for the API and serves the frontend from the backend container unless you run the frontend dev server separately.

### Worker-only container
```bash
docker compose -f docker-compose.worker.yml up --build
```

## Configuration
Set values in `.env`. The defaults below are the runtime defaults used by `backend/app/config.py` when the variable is not set.

### Required for a real setup
- `PAPERLESS_BASE_URL`
- `PAPERLESS_API_TOKEN`
- `DATABASE_URL`
- `QDRANT_URL`
- `LLM_BASE_URL`

### All configuration parameters
| Variable | Default | Description |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | Log level for backend services. |
| `LOG_JSON` | `0` | Emit JSON logs when `1`. |
| `API_SLOW_REQUEST_LOG_MS` | `1200` | Log API requests slower than this (ms). |
| `WORKER_MAX_RETRIES` | `2` | Worker retry count per task. |
| `PAPERLESS_BASE_URL` | `` | Base URL for Paperless-ngx. |
| `PAPERLESS_API_TOKEN` | `` | Paperless-ngx API token. |
| `DATABASE_URL` | `` | SQLAlchemy DB URL for local persistence. |
| `QDRANT_URL` | `` | Qdrant HTTP endpoint. |
| `QDRANT_API_KEY` | `` | Qdrant API key (optional). |
| `REDIS_HOST` | `` | Redis host or host:port for queue mode. |
| `QUEUE_ENABLED` | `0` | Enable queue-backed worker processing. |
| `LLM_BASE_URL` | `` | OpenAI-compatible API base URL. |
| `LLM_API_KEY` | `` | API key for the LLM provider. |
| `TEXT_MODEL` | `` | Text model name for suggestions and summaries. |
| `EMBEDDING_MODEL` | `` | Embedding model name. |
| `EMBEDDING_BATCH_SIZE` | `16` | Embedding batch size. |
| `EMBEDDING_TIMEOUT_SECONDS` | `60` | Embedding request timeout. |
| `EMBEDDING_MAX_CHUNKS_PER_DOC` | `0` | Max chunks per doc (0 = no cap). |
| `EMBEDDING_MAX_INPUT_TOKENS` | `3000` | Max tokens per embedding request. |
| `QDRANT_COLLECTION` | `paperless_chunks` | Qdrant collection name. |
| `EMBED_ON_SYNC` | `0` | Run embeddings during sync when `1`. |
| `CHUNK_MODE` | `heuristic` | Chunking strategy. |
| `CHUNK_MAX_CHARS` | `1200` | Max characters per chunk. |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks. |
| `CHUNK_SIMILARITY_THRESHOLD` | `0.75` | Threshold for chunk merging. |
| `ENABLE_PDF_PAGE_EXTRACT` | `1` | Use PDF text extraction when Paperless page splits are missing. |
| `ENABLE_VISION_OCR` | `0` | Enable vision OCR pipeline. |
| `VISION_MODEL` | `` | Vision model name for OCR. |
| `VISION_OCR_PROMPT` | `` | Inline prompt override for vision OCR. |
| `VISION_OCR_PROMPT_PATH` | `` | Prompt file path for vision OCR. |
| `SUGGESTIONS_PROMPT_PATH` | `` | Prompt file path for suggestions. |
| `SUGGESTIONS_DEBUG` | `0` | Log extra suggestion debug info when `1`. |
| `SUGGESTIONS_MAX_INPUT_CHARS` | `12000` | Max chars sent to suggestions prompt. |
| `LARGE_DOC_PAGE_THRESHOLD` | `20` | Large-doc cutoff (pages). |
| `PAGE_NOTES_TIMEOUT_SECONDS` | `45` | Timeout for page notes calls. |
| `PAGE_NOTES_MAX_OUTPUT_TOKENS` | `300` | Max tokens for page notes output. |
| `SUMMARY_SECTION_PAGES` | `25` | Pages per summary section. |
| `SECTION_SUMMARY_MAX_INPUT_TOKENS` | `6000` | Max input tokens per section summary. |
| `SECTION_SUMMARY_TIMEOUT_SECONDS` | `90` | Section summary timeout. |
| `GLOBAL_SUMMARY_MAX_INPUT_TOKENS` | `7000` | Max input tokens for global summary. |
| `GLOBAL_SUMMARY_TIMEOUT_SECONDS` | `120` | Global summary timeout. |
| `SUMMARY_MAX_OUTPUT_TOKENS` | `900` | Max output tokens for summaries. |
| `VISION_OCR_MIN_CHARS` | `40` | Minimum chars required to accept OCR result. |
| `VISION_OCR_MIN_SCORE` | `60` | Minimum OCR quality score to keep result. |
| `VISION_OCR_MAX_NONALNUM_RATIO` | `0.6` | Reject OCR if non-alnum ratio exceeds this. |
| `VISION_OCR_MAX_PAGES` | `0` | Max pages for vision OCR (0 = no cap). |
| `VISION_OCR_TIMEOUT_SECONDS` | `120` | Timeout per vision OCR request. |
| `VISION_OCR_MAX_DIM` | `1024` | Max image dimension for OCR rendering. |
| `VISION_OCR_TARGET_DIM` | `0` | Target resize dim (0 = disabled). |
| `VISION_OCR_BATCH_PAGES` | `1` | Pages per OCR request. |
| `HTTPX_VERIFY_TLS` | `1` | Verify TLS for outbound HTTPX requests. |
| `OCR_CHAT_BASE` | `` | Base URL for OCR quality scoring (chat). |
| `OCR_VISION_BASE` | `` | Base URL for OCR vision calls. |
| `OCR_SCORE_MODEL` | `` | Model override for OCR scoring. |
| `OCR_THRESH_BAD` | `55` | OCR "bad" threshold (higher = worse). |
| `OCR_THRESH_BORDERLINE` | `32` | OCR "borderline" threshold. |
| `OCR_ENABLE_LOGPROB_PPL` | `1` | Enable logprob/perplexity scoring. |
| `OCR_PPL_MAX_PROMPT_CHARS` | `20000` | Max chars sent to OCR scoring prompt. |
| `OCR_PPL_CHUNK_CHARS` | `4000` | Chunk size for OCR scoring. |
| `OCR_PPL_TIMEOUT_SEC` | `120` | Timeout for OCR scoring calls. |
| `OCR_VISION_TIMEOUT_SEC` | `180` | Timeout for OCR vision agreement calls. |
| `OCR_VISION_MAX_TOKENS` | `1200` | Max tokens for OCR vision agreement. |
| `STATUS_STREAM_INTERVAL_SECONDS` | `5` | Status stream poll interval. |
| `STATUS_LLM_MODELS_TTL_SECONDS` | `60` | Cache TTL for model status. |
| `EVIDENCE_MAX_PAGES` | `3` | Max pages searched for evidence. |
| `EVIDENCE_MIN_SNIPPET_CHARS` | `20` | Min snippet length for evidence. |
| `WORKER_SUGGESTIONS_MAX_CHARS` | `12000` | Max chars sent to worker suggestions. |
| `WRITEBACK_EXECUTE_ENABLED` | `0` | Enable writeback execution when `1`. |

## Docker-specific parameters
| Variable | Default | Description |
| --- | --- | --- |
| `FRONTEND_DIST` | `` | Path to prebuilt frontend assets inside the container. |

## Important docs
- `agents.md`: compact project state + next actions.
- `CHANGELOG.md`: granular change history.
- `MANUAL.md`: usage/ops details.
- `CONTRIBUTING.md`: how to contribute.
- `docs/execution-blueprint-large-doc-worker.md`: large-document worker strategy.

## API/client generation
```bash
cd frontend
ORVAL_API_URL=http://localhost:8000/api/openapi.json npm run api:generate
```

## License
MIT License. See `LICENSE`.
Provided “as is”, without warranty of any kind.
