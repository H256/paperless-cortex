# Paperless-NGX Cortex

Paperless-NGX Cortex is a separate intelligence layer for Paperless-ngx.
It keeps Paperless as source-of-truth, processes documents locally (sync, OCR layers, embeddings, suggestions), and supports explicit manual writeback only.

## Current Status (where we stand)

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

## Recent behavior notes
- `Writeback > Preview (only changed)` now collects candidates from local apply-audit + pending tags, not only first-page Paperless listing.
- Successful writeback no longer causes false `Sync: Missing` due to stale Paperless cache reads.
- Suggestions support summary-only regeneration (`Suggest new` on Summary) per source.
- Field variants are shown inline directly below each field in Suggestions.

## Quick start (dev)

### Backend
```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
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

## Docker
- App-only: `docker compose -f docker-compose.app.yml up --build`
- Full stack: `docker compose -f docker-compose.full.yml up --build`
- Worker-only: `docker compose -f docker-compose.worker.yml up --build`

## Important docs
- `agents.md`: compact project state + next actions.
- `CHANGELOG.md`: granular change history.
- `MANUAL.md`: usage/ops details.
- `docs/execution-blueprint-large-doc-worker.md`: large-document worker strategy.

## API/client generation
```bash
cd frontend
ORVAL_API_URL=http://localhost:8000/api/openapi.json npm run api:generate
```
