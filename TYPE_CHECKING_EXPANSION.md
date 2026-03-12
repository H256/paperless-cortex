# Type Checking Expansion Progress

## Verified state

- Current configured `mypy` coverage: **145 source files**
- Previous verified state in this branch before the follow-up slice: **41 source files**
- Net change in the latest follow-up slices: **46 -> 145 files**
- Net change from the original writeback-only baseline described in the review notes: **8 -> 145 files**
- Backend Python files currently present: **154**
- Current strict-checked share of backend Python files: **100%** (`145 / 145`)

## Files added in this slice

- `backend/app/routes/connections.py`
- `backend/app/routes/meta.py`
- `backend/app/routes/sync.py`
- `backend/app/routes/documents_actions.py`
- `backend/app/services/integrations/paperless.py`

## Supporting fixes required by the expansion

- Consolidated ingestion models into `backend/app/api_models.py` and removed `backend/app/schemas.py`.
- Added explicit return annotations on newly checked routes to satisfy `disallow_untyped_defs`.
- Added typed sync/reference caches in `sync.py`, `documents_actions.py`, and `worker.py`.
- Tightened `/status` payload/cache typing so it can remain in the checked set.
- Fixed newly surfaced type issues in `backend/app/services/writeback/writeback_apply.py`.

## Validation

Commands run successfully:

```bash
cd backend
uv run mypy --config-file pyproject.toml
uv run ruff check app/routes/connections.py app/routes/meta.py app/services/integrations/paperless.py app/routes/sync.py app/routes/documents_actions.py app/services/writeback/writeback_apply.py app/worker.py
uv run pytest tests/test_sync_meta_connections_routes.py tests/test_status_routes.py tests/test_documents_routes.py
```

## Notes

- This file reflects only verified results from the current working tree.
- Repo-wide Ruff for `backend/app` is now clean; `uv run ruff check app` passes.

## Adjacent cleanup completed after expansion

- `backend/app/routes/embeddings.py`
- `backend/app/services/search/embeddings.py`
- `backend/app/services/ai/chat.py`
- `backend/app/services/writeback/writeback_execution.py`
- `backend/app/services/documents/page_text_store.py`
- `backend/app/services/ai/suggestion_store.py`
- `backend/app/services/pipeline/queue.py`
- `backend/app/models.py`
- `backend/app/services/documents/text_pages.py`
- `backend/app/routes/documents.py`
- `backend/app/routes/documents_suggestions.py`
- `backend/app/services/writeback/writeback_direct.py`
- `backend/app/services/pipeline/task_runs.py`
- `backend/app/routes/chat.py`
- `backend/app/routes/documents_common.py`
- `backend/app/routes/queue_guard.py`
- `backend/app/services/runtime/time_utils.py`
- `backend/app/services/runtime/logging_setup.py`
- `backend/app/services/search/evidence.py`
- `backend/app/routes/documents_similarity.py`
- `backend/app/services/integrations/meta_cache.py`
- `backend/app/services/integrations/meta_sync.py`
- `backend/app/services/search/similarity.py`
- `backend/app/services/search/evidence_index.py`
- `backend/app/routes/queue.py`
- `backend/app/routes/writeback_dryrun.py`
- `backend/app/services/ai/hierarchical_generation.py`
- `backend/app/services/ai/hierarchical_storage.py`
- `backend/app/services/ai/hierarchical_summary_pipeline.py`
- `backend/app/services/ai/llm_client.py`
- `backend/app/services/ai/vision_ocr.py`
- `backend/app/services/documents/dashboard.py`
- `backend/app/services/documents/documents.py`
- `backend/app/services/pipeline/process_missing.py`
- `backend/app/services/pipeline/sync_state.py`

These files were not added to the strict mypy allowlist in this slice, but they were brought to targeted Ruff-clean state and validated with backend tests to keep the next expansion step smaller.

## Latest verified Ruff state

- Repo-wide Ruff findings were reduced further from **104** to **0**.
- `uv run ruff check app` now passes for the backend app package.

## Latest verified typing expansion

- Additional files brought into the strict mypy allowlist after the earlier 46-file checkpoint:
  - `backend/app/services/ai/ocr_scoring.py`
  - `backend/app/services/ai/suggestions.py`
  - `backend/app/services/ai/vision_ocr.py`
  - `backend/app/services/ai/hierarchical_generation.py`
  - `backend/app/services/ai/hierarchical_summary.py`
  - `backend/app/services/ai/hierarchical_summary_pipeline.py`
  - `backend/app/services/documents/dashboard.py`
  - `backend/app/services/documents/text_pages.py`
  - `backend/app/services/integrations/connections.py`
  - `backend/app/services/pipeline/pipeline_fanout.py`
  - `backend/app/services/pipeline/pipeline_planner.py`
  - `backend/app/services/pipeline/queue_tasks.py`
  - `backend/app/services/runtime/guard.py`
  - `backend/app/services/search/embedding_init.py`
  - `backend/app/routes/chat.py`
  - `backend/app/routes/documents_common.py`
  - `backend/app/routes/documents_similarity.py`
  - `backend/app/routes/queue.py`
  - `backend/app/routes/queue_guard.py`
  - `backend/app/main.py`
  - `backend/app/version.py`
  - `backend/app/services/search/evidence.py`
  - `backend/app/routes/documents.py`
  - `backend/app/routes/documents_suggestions.py`
  - `backend/app/routes/embeddings.py`
  - `backend/app/services/search/embeddings.py`
  - `backend/app/services/pipeline/process_missing.py`
  - `backend/app/services/ai/chat.py`
  - `backend/app/__init__.py`
  - `backend/app/routes/__init__.py`
  - `backend/app/services/ai/__init__.py`
  - `backend/app/services/documents/__init__.py`
  - `backend/app/services/integrations/__init__.py`
  - `backend/app/services/pipeline/__init__.py`
  - `backend/app/services/runtime/__init__.py`
  - `backend/app/services/search/__init__.py`
  - `backend/app/services/writeback/__init__.py`
  - `backend/tests/test_json_utils.py`
  - `backend/tests/test_note_ids.py`
  - `backend/tests/test_string_list_json.py`
  - `backend/tests/test_worker_error_types.py`
  - `backend/tests/test_worker_checkpoint_recovery.py`
  - `backend/tests/test_writeback_plan.py`
  - `backend/tests/test_writeback_selection_service.py`
  - `backend/app/services/pipeline/queue.py`
  - `backend/tests/test_qdrant_service.py`
  - `backend/tests/test_similarity_service.py`
  - `backend/tests/test_writeback_preview_service.py`
  - `backend/tests/test_task_runs_service.py`
  - `backend/tests/test_chat_routes.py`
  - `backend/tests/test_status_routes.py`
  - `backend/tests/test_meta_sync.py`
  - `backend/tests/test_sync_upsert_notes.py`
  - `backend/tests/test_documents_suggestions_routes.py`
  - `backend/tests/test_writeback_direct_service.py`
  - `backend/tests/test_queue_resilience.py`
  - `backend/tests/test_queue_stats_self_heal.py`
  - `backend/tests/test_pipeline_similarity_index.py`
  - `backend/tests/test_worker_vision_suggestions.py`
  - `backend/tests/test_writeback_apply_service.py`
  - `backend/tests/test_embedding_chunk_budget.py`
  - `backend/tests/test_hierarchical_summary_parsing.py`
  - `backend/tests/test_pipeline_fanout_service.py`
  - `backend/tests/test_evidence_service.py`
  - `backend/tests/test_chat_evidence_routes.py`
  - `backend/tests/test_sync_meta_connections_routes.py`
  - `backend/tests/test_large_doc_processing.py`
  - `backend/tests/test_queue_delayed_routes.py`
  - `backend/tests/test_queue_dlq_routes.py`
  - `backend/tests/test_worker_resume_checkpoint.py`
  - `backend/tests/test_worker_retry_checkpoint_sequence.py`
  - `backend/tests/test_queue_task_runs_routes.py`
  - `backend/tests/test_chat_service_evidence.py`
  - `backend/tests/test_writeback_dryrun_routes.py`
  - `backend/tests/test_writeback_jobs_routes.py`
  - `backend/tests/conftest.py`
  - `backend/alembic/env.py`
  - `backend/scripts/export_openapi.py`
  - `backend/tests/test_documents_routes.py`
  - `backend/tests/test_embeddings_routes.py`
  - `backend/tests/test_meta_routes.py`
  - `backend/tests/test_connections_service.py`
  - `backend/tests/test_queue_routes_basic.py`
  - `backend/tests/test_sync_routes_state.py`
  - `backend/tests/test_documents_actions_routes.py`
  - `backend/tests/test_connections_routes.py`
  - `backend/tests/test_sync_documents_routes.py`
  - `backend/tests/test_process_missing_service.py`

## Latest verified validation

Commands run successfully:

```bash
cd backend
uv run mypy --config-file pyproject.toml
uv run ruff check app app/routes/queue.py tests/test_qdrant_service.py tests/test_similarity_service.py tests/test_writeback_preview_service.py tests/test_task_runs_service.py tests/test_chat_routes.py tests/test_status_routes.py tests/test_meta_sync.py tests/test_sync_upsert_notes.py tests/test_documents_suggestions_routes.py tests/test_writeback_direct_service.py
uv run pytest tests/test_qdrant_service.py tests/test_similarity_service.py tests/test_writeback_preview_service.py tests/test_task_runs_service.py tests/test_queue_resilience.py tests/test_queue_stats_self_heal.py
uv run pytest tests/test_chat_routes.py tests/test_status_routes.py tests/test_meta_sync.py tests/test_sync_upsert_notes.py tests/test_documents_suggestions_routes.py tests/test_writeback_direct_service.py
uv run ruff check app/services/writeback/writeback_apply.py app/services/documents/text_cleaning.py app/services/runtime/time_utils.py app/services/integrations/meta_cache.py
uv run pytest tests/test_writeback_apply_service.py tests/test_queue_resilience.py tests/test_queue_stats_self_heal.py tests/test_pipeline_similarity_index.py
uv run ruff check app/routes/writeback_dryrun.py app/services/pipeline/task_runs.py tests/test_embedding_chunk_budget.py tests/test_hierarchical_summary_parsing.py tests/test_pipeline_fanout_service.py
uv run pytest tests/test_writeback_jobs_routes.py tests/test_pipeline_fanout_service.py tests/test_embedding_chunk_budget.py tests/test_hierarchical_summary_parsing.py
uv run ruff check app/services/ai/llm_client.py app/services/documents/text_pages.py tests/test_evidence_service.py tests/test_chat_evidence_routes.py tests/test_sync_meta_connections_routes.py
uv run pytest tests/test_evidence_service.py tests/test_chat_evidence_routes.py tests/test_sync_meta_connections_routes.py tests/test_embedding_chunk_budget.py tests/test_hierarchical_summary_parsing.py
uv run ruff check app/services/ai/ocr_scoring.py app/services/ai/suggestions.py app/services/search/embeddings.py app/services/search/evidence.py app/services/pipeline/pipeline_fanout.py app/services/ai/vision_ocr.py app/services/writeback/writeback_execution.py app/services/ai/hierarchical_summary_pipeline.py app/worker.py
uv run pytest tests/test_embedding_chunk_budget.py tests/test_chat_service_evidence.py tests/test_evidence_service.py tests/test_worker_vision_suggestions.py
uv run pytest tests/test_pipeline_fanout_service.py tests/test_worker_vision_suggestions.py tests/test_writeback_jobs_routes.py tests/test_worker_checkpoint_recovery.py tests/test_worker_error_types.py
uv run pytest tests/test_hierarchical_summary_parsing.py tests/test_worker_vision_suggestions.py tests/test_writeback_jobs_routes.py
uv run pytest tests/test_large_doc_processing.py tests/test_queue_delayed_routes.py tests/test_queue_dlq_routes.py
uv run pytest tests/test_worker_resume_checkpoint.py tests/test_worker_retry_checkpoint_sequence.py tests/test_queue_task_runs_routes.py
uv run pytest tests/test_chat_service_evidence.py
uv run ruff check tests/test_writeback_dryrun_routes.py
uv run pytest tests/test_writeback_dryrun_routes.py
uv run ruff check tests/test_writeback_jobs_routes.py tests/test_documents_routes.py tests/test_writeback_dryrun_routes.py tests/conftest.py scripts/export_openapi.py alembic/env.py
uv run pytest tests/test_writeback_jobs_routes.py
uv run pytest tests/test_documents_routes.py
uv run ruff check tests/test_embeddings_routes.py
uv run pytest tests/test_embeddings_routes.py
uv run ruff check tests/test_meta_routes.py tests/test_connections_service.py
uv run pytest tests/test_meta_routes.py tests/test_connections_service.py
uv run ruff check tests/test_queue_routes_basic.py
uv run pytest tests/test_queue_routes_basic.py
uv run ruff check tests/test_sync_routes_state.py
uv run pytest tests/test_sync_routes_state.py
uv run ruff check tests/test_documents_actions_routes.py
uv run pytest tests/test_documents_actions_routes.py
uv run ruff check tests/test_connections_routes.py
uv run pytest tests/test_connections_routes.py
uv run ruff check tests/test_sync_documents_routes.py
uv run pytest tests/test_sync_documents_routes.py
uv run ruff check tests/test_process_missing_service.py
uv run mypy --config-file pyproject.toml tests/test_process_missing_service.py
uv run pytest tests/test_process_missing_service.py
uv run mypy --config-file pyproject.toml
uv run pytest tests/test_embeddings_routes.py tests/test_sync_documents_routes.py tests/test_process_missing_service.py
```

## Latest adjacent structured logging validation

- Structured request and worker logging foundation completed in the current branch without changing the strict mypy count.
- Verified with:
  - `cd backend && uv run ruff check app/services/runtime/logging_setup.py app/main.py app/routes/chat.py app/worker.py tests/test_logging_setup.py tests/test_request_logging.py`
  - `cd backend && uv run mypy --config-file pyproject.toml app/services/runtime/logging_setup.py app/main.py app/routes/chat.py app/worker.py tests/test_logging_setup.py tests/test_request_logging.py`
  - `cd backend && uv run pytest tests/test_logging_setup.py tests/test_request_logging.py tests/test_status_routes.py tests/test_chat_routes.py tests/test_worker_error_types.py`
  - `cd backend && uv run mypy --config-file pyproject.toml`
  - `cd backend && uv run ruff check app`

## Latest coverage follow-through after structured logging

- Added `backend/tests/test_process_missing_route.py` for direct `documents_actions` process-missing route coverage.
- Added `backend/tests/test_logging_setup.py` and `backend/tests/test_request_logging.py` to the strict mypy allowlist.
- Verified with:
  - `cd backend && uv run ruff check tests/test_process_missing_route.py tests/test_logging_setup.py tests/test_request_logging.py`
  - `cd backend && uv run mypy --config-file pyproject.toml tests/test_process_missing_route.py tests/test_logging_setup.py tests/test_request_logging.py`
  - `cd backend && uv run pytest tests/test_process_missing_route.py tests/test_logging_setup.py tests/test_request_logging.py tests/test_documents_actions_routes.py`
  - `cd backend && uv run mypy --config-file pyproject.toml`

## Latest configuration-management expansion

- Added `backend/tests/test_config.py` to the strict mypy allowlist.
- Refactored `backend/app/config.py` to expose validated domain config views while preserving the existing flat `Settings` field API for downstream compatibility.
- Added explicit parsing/validation helpers for booleans, integers, floats, optional strings, database URLs, and `CHUNK_MODE`.
- Verified with:
  - `cd backend && uv run ruff check app/config.py tests/test_config.py`
  - `cd backend && uv run mypy --config-file pyproject.toml app/config.py tests/test_config.py`
  - `cd backend && uv run pytest tests/test_config.py tests/test_status_routes.py tests/test_request_logging.py tests/test_qdrant_service.py`
  - `cd backend && uv run mypy --config-file pyproject.toml`

## Latest service-layer extraction expansion

- Added `backend/app/services/documents/operations.py` to the strict mypy allowlist.
- Extracted the `documents_actions` pipeline orchestration and cleanup-text execution logic into the new service module while preserving route-level behavior.
- Verified with:
  - `cd backend && uv run ruff check app/routes/documents_actions.py app/services/documents/operations.py`
  - `cd backend && uv run mypy --config-file pyproject.toml app/routes/documents_actions.py app/services/documents/operations.py`
  - `cd backend && uv run pytest tests/test_documents_actions_routes.py tests/test_process_missing_route.py tests/test_documents_routes.py`
  - `cd backend && uv run mypy --config-file pyproject.toml`

## Latest documents read-model extraction expansion

- Added `backend/app/services/documents/read_models.py` to the strict mypy allowlist.
- Extracted the `documents.py` list/local-read shaping helpers into the new service module while preserving route-level behavior and reusing the same read-model seam from `documents_similarity.py`.
- Verified with:
  - `cd backend && uv run ruff check app/routes/documents.py app/routes/documents_similarity.py app/services/documents/read_models.py`
  - `cd backend && uv run mypy --config-file pyproject.toml app/routes/documents.py app/routes/documents_similarity.py app/services/documents/read_models.py`
  - `cd backend && uv run mypy --config-file pyproject.toml`
  - `cd backend && uv run pytest tests/test_documents_routes.py tests/test_similarity_service.py tests/test_pipeline_similarity_index.py`

## Latest sync extraction expansion

- Added `backend/app/services/documents/sync_operations.py` to the strict mypy allowlist.
- Extracted the `sync.py` document-sync orchestration, note merge logic, document upsert logic, and embedding execution into the new service module while preserving route-level behavior and sync test coverage.
- Verified with:
  - `cd backend && uv run ruff check app/routes/sync.py app/services/documents/sync_operations.py tests/test_sync_upsert_notes.py tests/test_sync_routes_state.py tests/test_sync_documents_routes.py tests/test_sync_meta_connections_routes.py`
  - `cd backend && uv run mypy --config-file pyproject.toml app/routes/sync.py app/services/documents/sync_operations.py tests/test_sync_upsert_notes.py tests/test_sync_routes_state.py tests/test_sync_documents_routes.py tests/test_sync_meta_connections_routes.py`
  - `cd backend && uv run mypy --config-file pyproject.toml`
  - `cd backend && uv run pytest tests/test_meta_sync.py tests/test_sync_upsert_notes.py tests/test_sync_routes_state.py tests/test_sync_documents_routes.py tests/test_sync_meta_connections_routes.py`

## Latest query-optimization verification

- The strict mypy allowlist count remains `143` after the low-risk eager-loading optimization pass.
- Verified the optimized document/similarity/writeback query paths with:
  - `cd backend && uv run ruff check app/routes/documents.py app/routes/documents_similarity.py app/services/search/similarity.py app/services/writeback/writeback_preview.py app/routes/writeback_dryrun.py`
  - `cd backend && uv run mypy --config-file pyproject.toml app/routes/documents.py app/routes/documents_similarity.py app/services/search/similarity.py app/services/writeback/writeback_preview.py app/routes/writeback_dryrun.py`
  - `cd backend && uv run pytest tests/test_documents_routes.py tests/test_similarity_service.py tests/test_writeback_preview_service.py`
  - `cd backend && uv run pytest tests/test_writeback_jobs_routes.py tests/test_writeback_dryrun_routes.py`
  - `cd backend && uv run mypy --config-file pyproject.toml`

## Latest tooling-enforcement verification

- The strict mypy allowlist count remains `143` after the backend CI and pre-commit enforcement changes.
- Verified the enforced tooling commands with:
  - `uv run --project backend pre-commit validate-config`
  - `uv run --project backend pre-commit run check-yaml --files .pre-commit-config.yaml .github/workflows/backend-ci.yml`
  - `cd backend && uv run --project backend ruff check app tests scripts alembic`
  - `cd backend && uv run --project backend mypy --config-file pyproject.toml`
  - `cd backend && uv run --project backend pytest`

## Latest error-observability expansion

- Added `backend/tests/test_api_error_responses.py` to the strict mypy allowlist.
- The strict mypy allowlist count is now `144`.
- Verified the centralized error-response/observability changes with:
  - `cd backend && uv run ruff check app/main.py tests/test_api_error_responses.py tests/test_request_logging.py`
  - `cd backend && uv run mypy --config-file pyproject.toml app/main.py tests/test_api_error_responses.py`
  - `cd backend && uv run pytest tests/test_api_error_responses.py tests/test_request_logging.py tests/test_status_routes.py`
  - `cd backend && uv run mypy --config-file pyproject.toml`

## Latest client-pooling expansion

- Added `backend/tests/test_http_client_pooling.py` to the strict mypy allowlist.
- The strict mypy allowlist count is now `145`.
- Verified the client-pooling/performance slice with:
  - `cd backend && uv run ruff check app/services/integrations/paperless.py app/services/search/qdrant.py app/services/ai/llm_client.py tests/test_http_client_pooling.py app/services/integrations/connections.py`
  - `cd backend && uv run mypy --config-file pyproject.toml`
  - `cd backend && uv run pytest tests/test_http_client_pooling.py tests/test_connections_service.py tests/test_qdrant_service.py tests/test_status_routes.py`
