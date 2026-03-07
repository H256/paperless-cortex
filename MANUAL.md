# Paperless-NGX Cortex Manual

## 1. What this app is
Paperless-NGX Cortex is a local intelligence layer for Paperless-ngx. This manual expands on `README.md` with more detailed setup and operations guidance.

- Paperless remains source-of-truth.
- Cortex syncs, analyzes, embeds, and suggests locally.
- Writeback is explicit/manual (never automatic).

## 2. Start the app (local development)

### Prerequisites
- Python `>=3.13` for the backend.
- Node.js `>=18` for the frontend.
- Paperless-ngx instance reachable by URL and API token.
- Postgres, Redis, and Qdrant (local installs or Docker).
- An OpenAI-compatible LLM endpoint (local or remote).

### Backend
```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

### Backend (pip alternative)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Worker (queue mode)
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

### Default dev URLs
- Backend API: `http://localhost:8000`
- Frontend: `http://localhost:5173`
In Docker, the API is still `:8000`, and the frontend is served by the backend container on the same port unless you run the frontend dev server separately.

## 3. Alembic quick usage

### Apply migrations
```bash
cd backend
uv run alembic upgrade head
```

### Create a new migration
```bash
cd backend
uv run alembic revision --autogenerate -m "describe_change"
```

### Show current migration
```bash
cd backend
uv run alembic current
```

## 4. Docker usage

### App-only stack
```bash
docker compose -f docker-compose.app.yml up --build
```

### Full stack (app + postgres + redis + qdrant)
```bash
docker compose -f docker-compose.full.yml up --build
```
You must set `LLM_BASE_URL` in `.env` before starting the full stack.

### Worker-only container
```bash
docker compose -f docker-compose.worker.yml up --build
```

## 5. Environment basics
- Copy `.env.example` to `.env` and fill values.
- For worker-specific tuning, use `.env.worker.example` as reference.
- Minimum important values:
  - `PAPERLESS_BASE_URL`
  - `PAPERLESS_API_TOKEN`
  - `DATABASE_URL`
  - `QDRANT_URL`
  - `LLM_BASE_URL`
- Model selection:
  - `TEXT_MODEL` is used for suggestions/summaries and as chat fallback.
  - `CHAT_MODEL` is optional and, when set, is used for chat instead of `TEXT_MODEL`.

## 6. Database setup
1. Create the database specified by `DATABASE_URL`.
2. Run Alembic migrations.

Example Postgres setup:
```bash
createdb paperless_intelligence
createuser paperless
```

Apply migrations:
```bash
cd backend
uv run alembic upgrade head
```

## 7. Main processing flow
1. Sync docs from Paperless.
2. Build/refresh OCR layers (paperless baseline, optional vision).
3. Build embeddings (paperless/vision strategy).
4. Generate suggestions.
5. For large docs: page notes + hierarchical summary.
6. Review locally.
7. Write back manually when wanted.

## 8. Page-by-page guide

### Dashboard (`/dashboard`)
Purpose: high-level status and processing overview.
Use it for:
- processed/unprocessed counts
- trend and distribution checks
- quick health pulse

### Documents (`/documents`)
Purpose: primary work queue.
Use it for:
- filtering and triage
- opening document details
- launching continue processing flows

Tips:
- use filters first, then open details in context
- use continue-processing tools for missing steps

### Document Detail (`/documents/:id`)
Purpose: full per-document inspection and control center.

Tabs:
- `Metadata`: current local/Paperless values
- `Text & quality`: text layers + OCR quality metrics
- `Suggestions`: paperless/vision suggestions, variants, apply actions, plus similar-doc metadata hints
- `Pages`: per-page text and page-level inspection
- `Chat`: document chat with follow-up questions and relationship mode (chrono)
- `Similar`: top-10 similar documents + possible duplicates (display + refresh)
- `Operations`: per-doc pipeline actions, fan-out, timeline, retries

Key actions:
- Continue missing processing (doc-specific)
- Queue single steps manually (including `similarity_index`)
- Retry failed runs from timeline
- Write back local reviewed changes manually

### Search (`/search`)
Purpose: semantic retrieval.
Use it for:
- embeddings-based lookup
- source filtering (`paperless_ocr`, `vision_ocr`, `pdf_text`)
- quick jump to document details with page/bbox

Shortcuts:
- `/` focus query
- `Ctrl+Enter` run search
- `Ctrl+Shift+Enter` open first result

### Chat (`/chat`)
Purpose: retrieval + answer with citations.
Use it for:
- follow-up Q/A with conversation continuity
- citation jumps to document details/new tab
- quick source validation

Shortcuts:
- `/` focus question
- `Ctrl+Enter` ask
- `Ctrl+Shift+Enter` open first citation from latest answer

### Writeback (`/writeback`)
Purpose: controlled manual writeback workflow.
Use it for:
- previewing changes
- selecting document set
- executing explicit writeback only when approved

### Queue (`/queue`)
Purpose: worker queue control.
Use it for:
- inspect queued/running tasks
- reordering tasks
- retrying failed tasks
- DLQ/delayed task handling

### Logs (`/logs`)
Purpose: operational troubleshooting.
Use it for:
- filtering by task/error type
- isolating failures quickly
- understanding retryability and error categories

### Operations (`/operations`)
Purpose: maintenance/admin actions.
Use it for:
- destructive maintenance actions (with caution)
- targeted similarity-index reset (`Reset similarity index`) to drop doc-level similarity vectors + similarity task history before rebuilding
- runtime config checks
- sync/embed status checks
- worker lock/queue maintenance

### Continue Processing (`/processing/continue`)
Purpose: bulk missing-work orchestration.
Use it for:
- dry-run preview of missing tasks
- selecting processing strategy
- enqueueing only missing pipeline steps

## 9. Recommended daily workflow
1. Open `Documents` and filter to your review queue.
2. Run `Continue processing` for missing work.
3. Inspect in `Document Detail` (suggestions + timeline).
4. Validate with `Search`/`Chat` when needed.
5. Execute manual `Writeback` only for reviewed docs.
6. Use `Queue`/`Logs` for failures.

## 10. Troubleshooting quick checks
- API unreachable: verify backend running on `:8000`.
- No processing movement: verify worker is running and queue enabled.
- Missing embeddings/suggestions: run continue-processing and inspect fan-out in detail page.
- Writeback unavailable: verify local changes/review status in detail page.

## 11. Related docs
- `README.md` - project overview and quick start
- `agents.md` - current phase and high-level working state
- `CHANGELOG.md` - granular change history with commit hashes
- `docs/execution-blueprint-large-doc-worker.md` - large-document processing details

## 12. Versioning (simple start, no CI)
A single root `VERSION` file is used for backend + frontend versioning.

```bash
python scripts/sync_version.py
```

The script updates:
- `backend/pyproject.toml`
- `frontend/package.json`
- `frontend/src/generated/version.ts`

The runtime versions are available via `GET /api/status` (`app_version`, `api_version`, `frontend_version`) and shown in the footer.
