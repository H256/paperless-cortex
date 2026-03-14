# Review Progress Summary

## Latest block

### CI test collection fix

- The backend test harness is now robust against import-order differences in CI: `backend/app/db.py` no longer requires `DATABASE_URL` just to import route or worker modules during pytest collection.
- Full backend verification is green again after aligning the stale vector-store connection test with the generic provider health-check seam.

### Chat async offload completion

- `6.1 Async/Await Optimization` is now effectively complete for this phase: the remaining low-risk async route hotspot in the chat surface no longer performs synchronous answer generation, follow-up generation, or evidence resolution directly on the async handler path.
- With `status` streaming already offloaded and the chat routes now offloading their synchronous retrieval/generation work through `asyncio.to_thread(...)`, the obvious request-path event-loop blockers from Claude’s review are closed for this phase.

### Continue-processing diagnostics extraction

- `4.1 Component Organization` moved again: the diagnostics-heavy portion of the continue-processing UI is no longer embedded directly in `frontend/src/components/ContinueProcessingPanel.vue`, and now lives behind the dedicated `frontend/src/components/ContinueProcessingDiagnosticsSection.vue` seam.
- `4.2 Frontend Testing` moved with it: the extracted diagnostics section now has direct integration coverage, while the surrounding continue-processing panel/view regressions remain green.

### Documents mutation extraction

- `3.4 Reduce Import Complexity` moved again: `backend/app/routes/documents_actions.py` no longer owns the route-local vision-OCR and suggestion deletion mutation blocks, and now delegates those DB cleanup plus cache-invalidation flows through `backend/app/services/documents/document_mutations.py`.
- With those delete-path helpers extracted, the remaining import/coupling payoff in `documents_actions.py` is now small enough that `3.4` is close to done for this phase.

### Config redesign completion

- `3.1 Configuration Management` is now effectively complete for this phase: `backend/app/config.py` is no longer just a flat environment dump with helper properties layered on top, and now exposes real nested domain configs as the primary settings surface.
- The remaining app-level env toggles for frontend/static path and LLM debug behavior are now settings-backed instead of being re-read ad hoc in runtime modules, and startup validation now fails fast on invalid vector-store provider and queue/weaviate combinations.

### Page-text payload extraction

- `3.3 Service Layer Complexity` moved again: `backend/app/routes/documents.py` no longer owns the page-text payload aggregation and coverage calculation flow, and now delegates that read-model assembly through `backend/app/services/documents/page_texts_payload.py`.
- With both the suggestions route and the document page-text payload extracted, the remaining route/worker modules are now mostly thin wrappers or stable orchestration seams, so `3.3` is effectively complete for this phase.

### Suggestions route orchestration extraction

- `3.3 Service Layer Complexity` moved again: `backend/app/routes/documents_suggestions.py` no longer owns suggestion refresh orchestration, variant generation orchestration, similar-document enrichment, or apply-to-document mutation handling directly, and now delegates those flows through `backend/app/services/ai/suggestion_operations.py` and `backend/app/services/ai/suggestion_apply.py`.
- With the suggestions route now reduced to request validation plus HTTP response shaping, the remaining route-layer orchestration hotspots are much smaller and `3.3` is close to its credible finish line for this phase.

### Local document detail eager-loading

- `3.2 Database Query Optimization` is now effectively complete for this phase: the remaining local document detail hotspot no longer pays relationship lazy-load queries for tags, notes, correspondent, and document type after the prior aggregate-query reductions.
- At this point the major low-risk backend query wins from Claude’s review are in: task-run pagination, document list/detail aggregation, dashboard aggregation, writeback preview scoping, and local detail eager-loading.

### Tooling enforcement cleanup

- `5.2 Developer Tooling` is now effectively complete for this phase: local hooks and CI are aligned around the same backend/frontend quality gates instead of partially overlapping checks.
- The noisy frontend-on-backend CI trigger is gone, and pre-commit now enforces both frontend linting and frontend type-checking alongside backend mypy and formatting checks.

### Runtime metrics and telemetry

- `5.3 Error Messages & Observability` is now effectively complete for this phase: backend observability no longer stops at structured logs and stable API error codes, and now includes a queryable runtime metrics surface.
- The API now emits route-aware request counters, request timings, and slow-request counters, and the worker now emits success/retry/dead-letter/duration telemetry through the same in-memory metrics registry exposed at `/api/status/metrics`.

### LLM SDK client pooling

- `6.3 Connection Pooling` moved again: the OpenAI SDK client in `backend/app/services/ai/llm_client.py` is now pooled by base URL, API key, and timeout instead of being rebuilt for every chat or embedding call.
- With pooled Paperless, Qdrant, Weaviate, OCR-scoring, raw LLM `httpx`, and now SDK-level LLM clients in place, the obvious per-request integration client creation hotspots are closed for this phase.

### OCR scoring client pooling

- `6.3 Connection Pooling` is moving again: the OCR scoring path no longer creates a fresh `httpx.Client` for every prompt-logprob request, and now reuses a pooled client keyed by endpoint, timeout, and TLS settings.
- The new OCR scoring client-pool regression closes the obvious remaining per-request HTTP client hotspot in that AI helper path, so `6.3` has concrete progress again instead of only the earlier integration-client pooling slices.

### Vector-store deletion coverage

- `2.1 Increase Test Coverage` is now effectively complete for the highest-value backend refactor seams in this phase: the vector-store provider boundary now has direct regression coverage for provider routing and delete behavior instead of relying on indirect route tests.
- The Weaviate adapter now has direct deletion-path coverage for chunk collections, centroid collections, and missing-collection no-op behavior, which closes the remaining obvious backend gap introduced by the vector-store abstraction and Weaviate support.

### Process-missing route cleanup

- `3.4 Reduce Import Complexity` moved again: `backend/app/routes/documents_actions.py` no longer owns queue-disabled response shaping or `ProcessMissingOptions` construction for `/documents/process-missing`, and now delegates that request validation/building through `backend/app/services/documents/process_missing_request.py`.
- The focused process-missing/documents/documents-actions regressions still pass after that extraction, and the strict backend mypy baseline remains green on `176` configured files.

### Reset-and-reprocess route cleanup

- `3.4 Reduce Import Complexity` moved again: `backend/app/routes/documents_actions.py` no longer owns the reset-and-reprocess clear/sync/requeue flow directly, and now delegates that orchestration through `backend/app/services/documents/reprocess_request.py`.
- The focused documents-actions/documents regressions still pass after that extraction, and the strict backend mypy baseline remains green on `177` configured files.

### Enqueue-task route cleanup

- `3.4 Reduce Import Complexity` moved again: `backend/app/routes/documents_actions.py` no longer owns single-document enqueue-task validation or payload/response shaping, and now delegates that request logic through `backend/app/services/documents/document_task_request.py`.
- The focused documents/documents-actions regressions still pass after that extraction, and the strict backend mypy baseline remains green on `178` configured files.

### Cleanup-text route cleanup

- `3.4 Reduce Import Complexity` moved again: `backend/app/routes/documents_actions.py` no longer owns cleanup-text source validation or doc-id normalization, and now delegates that request shaping through `backend/app/services/documents/cleanup_text_request.py`.
- The focused documents-actions/documents regressions still pass after that extraction, and the strict backend mypy baseline remains green on `179` configured files.

### Worker task-execution cleanup

- `3.4 Reduce Import Complexity` moved again: `backend/app/worker.py` no longer owns task-run bookkeeping, retry/dead-letter handling, or failure classification directly, and now delegates that execution block through `backend/app/services/pipeline/worker_task_execution.py`.
- The focused worker runtime/retry/orchestration regressions still pass after that extraction, and the strict backend mypy baseline remains green on `180` configured files.

### Local document cache

- `6.2 Caching Strategy` moved again: `/documents/{doc_id}/local` now goes through `backend/app/services/documents/local_document_cache.py`, so repeated local detail payload reads reuse cached aggregations instead of rebuilding the full local status view every time.
- The local-document cache is now invalidated from the existing document mutation, sync, vector-maintenance, and writeback paths, and the focused document/sync/writeback regressions still pass with the strict backend mypy baseline green on `181` configured files.

### Page-texts cache

- `6.2 Caching Strategy` moved again: `/documents/{doc_id}/page-texts` now goes through `backend/app/services/documents/page_texts_cache.py`, so repeated page-text detail reads reuse the cached baseline/vision aggregation instead of reparsing that payload every time.
- The page-text cache is now invalidated from the direct text/vision stale paths, and the focused document/sync regressions still pass with the strict backend mypy baseline green on `182` configured files.

### Cache regression coverage

- `2.1 Increase Test Coverage` moved again: the document route regressions now explicitly pin both cache-heavy detail seams, covering stale page-text invalidation after `delete/vision-ocr` and stale local embedding flags after `delete/embeddings`.
- The focused documents/documents-actions regression set still passes after the new cache tests, so the recent `6.2` cache slices now have direct route-level protection instead of only relying on implementation reasoning.

### Worker execution coverage

- `2.1 Increase Test Coverage` moved again: the extracted worker execution bookkeeping seam is now directly covered in `backend/tests/test_worker_task_execution.py`, including retryable requeue behavior and non-retryable `VECTOR_CHUNKS_MISSING` dead-letter behavior.
- The focused worker execution/runtime/error-type regressions still pass after the new test file, so the recent `3.4` worker extraction now has direct behavioral coverage instead of only indirect route/loop coverage.

### Frontend component organization

- Extracted the document-detail header and action bar into `frontend/src/components/DocumentDetailHeader.vue`.
- Reduced `DocumentDetailView.vue` template sprawl without changing tab routing, back navigation, review, writeback, or reload behavior.
- Verified targeted frontend linting, typing, detail-view integration coverage, and production build output.
- Extracted the documents list title/overview/processing-toolbar cluster into `frontend/src/components/DocumentsHeaderSection.vue`.
- Added direct integration coverage for the new documents header seam and kept targeted frontend verification green.
- Added `frontend/src/views/DocumentsView.integration.test.ts` to cover page-level navigation wiring for processing actions, document detail links, operations/suggestions deep links, and empty-state processing CTA behavior.
- Frontend page-level coverage now explicitly protects the main document views touched by the refactor.
- Extracted the worker-lock and runtime-configuration cluster into `frontend/src/components/MaintenanceRuntimeSection.vue`, reducing `MaintenanceView.vue` to clearer page composition and dialog orchestration.
- Added direct integration coverage for the new maintenance runtime seam and kept the existing maintenance-view copy/runtime regression green.
- Extracted the queue header, control bar, status cards, running-task summary, and recent-run timeline into `frontend/src/components/QueueOverviewSection.vue`, reducing `QueueView.vue` to clearer queue-management page composition.
- Added direct integration coverage for the new queue overview seam and kept the broader frontend coverage run green at `77` passing tests.
- Added direct view-level integration coverage for `frontend/src/views/QueueView.vue`, so queue filtering, movement/removal actions, failed-run retry, and document navigation are pinned at the page boundary rather than only through section tests.
- Added direct view-level integration coverage for `frontend/src/views/ContinueProcessingView.vue`, so preview hydration and queue/log/document/back routing are now pinned at the page boundary too.
- Frontend coverage now passes with `79` tests after the new queue and continue-processing view regressions.
- `3.4 Reduce Import Complexity` moved again: `backend/app/routes/documents_suggestions.py` no longer imports shared suggestion-loading logic from another route module, and the old `backend/app/routes/documents_common.py` helper file has been deleted after that logic was absorbed into `backend/app/services/ai/suggestion_store.py`.
- The strict backend mypy baseline remains green after the cleanup on `164` configured files, and the affected document suggestion/document route regressions still pass.
- `3.4 Reduce Import Complexity` moved again: the queue-enabled guard now lives in `backend/app/services/pipeline/queue_access.py`, so `documents.py`, `documents_actions.py`, and `documents_suggestions.py` no longer depend on the deleted route-local helper `backend/app/routes/queue_guard.py`.
- The affected queue-enabled document route regressions still pass after the cleanup, and the strict backend mypy baseline remains green on `164` configured files.
- `3.4 Reduce Import Complexity` moved again: `backend/app/routes/writeback_dryrun.py` no longer owns its writeback job serialization and missing-table helper cluster directly, and now delegates that logic through `backend/app/services/writeback/writeback_jobs.py`.
- The focused writeback dry-run/job regressions still pass after the extraction, and the route contract remains unchanged.
- `3.4 Reduce Import Complexity` moved again: `backend/app/routes/queue.py` no longer depends on the deleted route-local helper `backend/app/routes/queue_helpers.py`, and now gets the queue-disabled response shape from `backend/app/services/pipeline/queue_responses.py`.
- The focused queue route/resilience regressions still pass after the cleanup, and the strict backend mypy baseline remains green on `164` configured files.
- `3.4 Reduce Import Complexity` moved again: `backend/app/routes/writeback_dryrun.py` no longer owns its writeback mutation side effects directly, and now delegates pending-row cleanup plus reviewed-timestamp refresh through `backend/app/services/writeback/writeback_effects.py`.
- The focused writeback preview/dry-run/job regressions still pass after that extraction, and the strict backend mypy baseline remains green on `165` configured files with the new service added to the allowlist.
- `3.4 Reduce Import Complexity` moved again: `backend/app/routes/writeback_dryrun.py` no longer owns direct-writeback document context assembly, and now delegates pending-row lookup, metadata hydration, and remote document fetches through `backend/app/services/writeback/writeback_context.py`.
- The focused writeback preview/dry-run/job regressions still pass after that extraction, and the strict backend mypy baseline remains green on `166` configured files with the new service added to the allowlist.
- `3.4 Reduce Import Complexity` moved again: `backend/app/routes/documents_actions.py` no longer reaches straight into low-level embedding/similarity deletion helpers, and now delegates vector maintenance mutations through `backend/app/services/search/vector_maintenance.py`.
- The focused document-actions/documents/vector-store regressions still pass after that extraction, and the strict backend mypy baseline remains green on `167` configured files with the new service added to the allowlist.
- `3.4 Reduce Import Complexity` moved again: `backend/app/routes/writeback_dryrun.py` no longer owns writeback preview page-selection and cached item-loading orchestration, and now delegates that flow through `backend/app/services/writeback/writeback_queries.py`.
- The focused writeback preview/dry-run/job regressions still pass after that extraction, and the strict backend mypy baseline remains green on `168` configured files with the new service added to the allowlist.
- `3.4 Reduce Import Complexity` moved again: the remaining writeback command flows in `backend/app/routes/writeback_dryrun.py` now delegate through `backend/app/services/writeback/writeback_commands.py`, `backend/app/services/writeback/writeback_job_ops.py`, and `backend/app/services/writeback/writeback_direct_execute.py`.
- `backend/app/routes/writeback_dryrun.py` is now effectively a thin route wrapper module, and the focused writeback preview/dry-run/job regressions still pass with the strict backend mypy baseline green on `171` configured files.
- `3.4 Reduce Import Complexity` moved again: `backend/app/routes/documents_actions.py` no longer owns the bulk intelligence reset/clear DB cleanup logic, and now delegates that behavior through `backend/app/services/documents/intelligence_cleanup.py`.
- The focused documents-actions/documents regressions still pass after that extraction, and the strict backend mypy baseline remains green on `172` configured files.
- `3.4 Reduce Import Complexity` moved again: `backend/app/worker.py` no longer owns the queue lifecycle plumbing, and now delegates worker client/lock/heartbeat/queue-maintenance/task-finalize behavior through `backend/app/services/pipeline/worker_queue_runtime.py`.
- The focused worker runtime/retry/orchestration regressions still pass after that extraction, and the strict backend mypy baseline remains green on `172` configured files.
- `3.4 Reduce Import Complexity` moved again: `backend/app/worker.py` no longer owns the dispatch-map table directly, and now delegates task-type to handler selection through `backend/app/services/pipeline/worker_dispatch.py`.
- The focused worker runtime/retry/orchestration regressions still pass after that extraction, and the strict backend mypy baseline remains green on `174` configured files.
- `3.4 Reduce Import Complexity` moved again: `backend/app/routes/documents_actions.py` no longer owns the local-document auto-sync/load fallback and now delegates that Paperless fetch/validate/upsert path through `backend/app/services/documents/document_loader.py`.
- The focused documents-actions/documents regressions still pass after that extraction, and the strict backend mypy baseline remains green on `175` configured files.

### Weaviate migration hardening

- Added documented Weaviate/vector-store settings to `.env.example`, including separate HTTP and gRPC endpoints plus a dedicated centroid collection.
- Hardened `/api/documents/delete/embeddings` so empty vector backends are treated as a successful no-op and the route always returns the full response-model shape.
- Added provider-level full chunk-vector deletion through the vector-store adapter boundary for both Qdrant and Weaviate.
- Hardened stale `similarity_index` worker jobs so missing chunk vectors in the active backend are classified as stable non-retryable `VECTOR_CHUNKS_MISSING` failures instead of noisy traceback/retry behavior.
- Added regression coverage for empty-backend deletes, Weaviate config defaults, and the new worker error classification.
- Verified full backend and frontend CI-equivalent commands.

### Async route hardening

- `GET /status/stream` now moves blocking status-payload work off the event loop via `asyncio.to_thread(...)`.
- Added explicit async coverage for the status stream offload path.
- Hardened chat-evidence route tests so they no longer depend on live PDF download behavior during full-suite runs.

## Completed in this session

### 1. API model consolidation

- Moved the Paperless ingestion models into `backend/app/api_models.py`.
- Removed `backend/app/schemas.py`.
- Updated backend and test imports to the consolidated model module.

### 2. Type-checking expansion

- Expanded configured `mypy` coverage from **41** to **46** files.
- Added strict typing coverage for key backend route modules:
  - `connections.py`
  - `meta.py`
  - `sync.py`
  - `documents_actions.py`
- Added strict typing coverage for `services/integrations/paperless.py`.

### 3. Follow-on type fixes

- Added explicit route return types where strict mypy required them.
- Added typed cache aliases for sync/document operation flows.
- Fixed allowlist breakages surfaced in:
  - `backend/app/routes/status.py`
  - `backend/app/services/writeback/writeback_apply.py`
  - `backend/app/worker.py`

### 4. Ruff reduction on embeddings/chat/search

- Cleaned `backend/app/routes/embeddings.py`.
- Cleaned `backend/app/services/search/embeddings.py`.
- Cleaned `backend/app/services/ai/chat.py`.
- Verified with targeted tests:
  - `tests/test_chat_routes.py`
  - `tests/test_chat_service_evidence.py`
  - `tests/test_embedding_chunk_budget.py`
- Reduced repo-wide Ruff findings from **158** to **130**.

### 5. Ruff reduction on writeback/queue/store models

- Cleaned `backend/app/services/writeback/writeback_execution.py`.
- Cleaned `backend/app/services/documents/page_text_store.py`.
- Cleaned `backend/app/services/ai/suggestion_store.py`.
- Cleaned `backend/app/services/pipeline/queue.py`.
- Cleaned `backend/app/models.py`.
- Verified with targeted tests:
  - `tests/test_writeback_jobs_routes.py`
  - `tests/test_queue_resilience.py`
  - `tests/test_queue_stats_self_heal.py`
  - `tests/test_documents_routes.py`
- Reduced repo-wide Ruff findings from **130** to **104**.

### 6. Ruff reduction on document routes/runtime/search helpers

- Cleaned `backend/app/services/documents/text_pages.py`.
- Cleaned `backend/app/routes/documents.py`.
- Cleaned `backend/app/routes/documents_suggestions.py`.
- Cleaned `backend/app/services/writeback/writeback_direct.py`.
- Cleaned `backend/app/services/pipeline/task_runs.py`.
- Cleaned `backend/app/routes/chat.py`.
- Cleaned `backend/app/routes/documents_common.py`.
- Cleaned `backend/app/routes/queue_guard.py`.
- Cleaned `backend/app/services/runtime/time_utils.py`.
- Cleaned `backend/app/services/runtime/logging_setup.py`.
- Cleaned `backend/app/services/search/evidence.py`.
- Cleaned `backend/app/routes/documents_similarity.py`.
- Cleaned `backend/app/services/integrations/meta_cache.py`.
- Cleaned `backend/app/services/integrations/meta_sync.py`.
- Cleaned `backend/app/services/search/similarity.py`.
- Cleaned `backend/app/services/search/evidence_index.py`.
- Verified with targeted tests:
  - `tests/test_chat_routes.py`
  - `tests/test_chat_service_evidence.py`
  - `tests/test_documents_routes.py`
  - `tests/test_sync_meta_connections_routes.py`
- Reduced repo-wide Ruff findings from **104** to **57**.

### 7. Ruff reduction on queue/writeback/hierarchical-summary and service helpers

- Cleaned `backend/app/routes/queue.py`.
- Cleaned `backend/app/routes/writeback_dryrun.py`.
- Cleaned `backend/app/services/ai/hierarchical_generation.py`.
- Cleaned `backend/app/services/ai/hierarchical_storage.py`.
- Cleaned `backend/app/services/ai/hierarchical_summary_pipeline.py`.
- Cleaned `backend/app/services/ai/llm_client.py`.
- Cleaned `backend/app/services/ai/vision_ocr.py`.
- Cleaned `backend/app/services/documents/dashboard.py`.
- Cleaned `backend/app/services/documents/documents.py`.
- Cleaned `backend/app/services/pipeline/process_missing.py`.
- Cleaned `backend/app/services/pipeline/sync_state.py`.
- Verified with targeted tests:
  - `tests/test_writeback_jobs_routes.py`
  - `tests/test_chat_service_evidence.py`
  - `tests/test_documents_routes.py`
  - `tests/test_queue_resilience.py`
- Reduced repo-wide Ruff findings from **57** to **0**.

### 8. Mypy expansion and first targeted exception-handling pass

- Expanded configured strict mypy coverage from **46** to **68** backend source files.
- Added the next verified strict batch:
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
- Fixed the surfaced strict-typing issue in `backend/app/services/pipeline/pipeline_planner.py` and a local redefinition in `backend/app/services/documents/text_pages.py`.
- Added explicit route/app return annotations and small type fixes in `backend/app/routes/chat.py`, `backend/app/routes/documents_similarity.py`, `backend/app/routes/queue.py`, `backend/app/main.py`, and `backend/app/version.py` so the stricter batch passes cleanly.
- Started `2.2 Improve Error Handling` with low-risk replacements of broad exception handlers in JSON parsing, integer coercion, and SQLAlchemy checkpoint fallbacks:
  - `backend/app/services/ai/json_extraction.py`
  - `backend/app/services/runtime/json_utils.py`
  - `backend/app/services/runtime/string_list_json.py`
  - `backend/app/services/writeback/writeback_plan.py`
  - `backend/app/services/ai/suggestions.py`
  - `backend/app/services/documents/note_ids.py`
  - `backend/app/services/pipeline/worker_checkpoint.py`
  - `backend/app/routes/documents_common.py`
  - `backend/app/routes/queue.py`
  - `backend/app/services/search/evidence.py`
- Reduced remaining `except Exception` sites from **104** to **83**.

### 9. Mypy expansion on documents, suggestions, and embeddings

- Expanded configured strict mypy coverage from **68** to **72** backend source files.
- Added the next verified strict batch:
  - `backend/app/routes/documents.py`
  - `backend/app/routes/documents_suggestions.py`
  - `backend/app/routes/embeddings.py`
  - `backend/app/services/search/embeddings.py`
- Added explicit route return annotations and small payload coercion helpers where strict mypy surfaced object-valued response map issues.
- Fixed a typed variable-shadowing issue in `backend/app/services/search/embeddings.py` so the page-chunk builder can stay in the strict set.
- Continued the low-risk `2.2` pass by narrowing known exception paths in `backend/app/routes/documents_suggestions.py`.
- Reduced remaining `except Exception` sites from **83** to **81**.

### 10. Mypy expansion on process-missing and queue exception cleanup

- Expanded configured strict mypy coverage from **72** to **73** backend source files.
- Added the next verified strict file:
  - `backend/app/services/pipeline/process_missing.py`
- Kept the attempted `queue.py` promotion out of the strict allowlist because the Redis client remains effectively untyped and would drag `worker.py` and queue route typing churn into this slice.
- Still advanced `2.2 Improve Error Handling` in `backend/app/services/pipeline/queue.py` by narrowing several broad exception handlers around import failure, JSON parsing, and integer/float coercion while preserving the fail-open queue behavior.
- Reduced remaining `except Exception` sites from **81** to **70**.

### 11. Mypy expansion on chat service

- Expanded configured strict mypy coverage from **73** to **74** backend source files.
- Added the next verified strict file:
  - `backend/app/services/ai/chat.py`
- Fixed a local loop-variable shadowing issue in the chat service that confused mypy around citation payload mutation.
- Widened the chat history input type from a concrete `list[dict[str, str]]` shape to a covariant sequence so the already-typed route models can call the service without casts.
- Narrowed one date parsing fallback in `backend/app/services/ai/chat.py` from a broad catch to `ValueError`.
- Reduced remaining `except Exception` sites from **70** to **69**.

### 12. Backend-wide coverage push past 60%

- Expanded configured strict mypy coverage from **78** to **94** backend source files.
- Added package/module support files:
  - `backend/app/__init__.py`
  - `backend/app/routes/__init__.py`
  - `backend/app/services/ai/__init__.py`
  - `backend/app/services/documents/__init__.py`
  - `backend/app/services/integrations/__init__.py`
  - `backend/app/services/pipeline/__init__.py`
  - `backend/app/services/runtime/__init__.py`
  - `backend/app/services/search/__init__.py`
  - `backend/app/services/writeback/__init__.py`
- Added smaller verified backend tests to the strict mypy allowlist:
  - `backend/tests/test_json_utils.py`
  - `backend/tests/test_note_ids.py`
  - `backend/tests/test_string_list_json.py`
  - `backend/tests/test_worker_error_types.py`
  - `backend/tests/test_worker_checkpoint_recovery.py`
  - `backend/tests/test_writeback_plan.py`
  - `backend/tests/test_writeback_selection_service.py`
- Added missing `-> None` test annotations in the small worker/writeback tests so they satisfy strict mypy without behavioral changes.
- Kept the broad `except Exception` total steady at **69** in this batch while focusing on the coverage milestone.

### 13. Focused exception cleanup in worker and document operations

- Continued `2.2 Improve Error Handling` on the concentrated backend hotspots without expanding the strict mypy allowlist further.
- Narrowed document-operation catches in `backend/app/routes/documents_actions.py` to concrete network, validation, database, and value-coercion errors for:
  - auto-sync of missing local documents
  - sync freshness checks
  - similarity-index deletion fallback
- Narrowed worker catches in `backend/app/worker.py` for:
  - rollback failures (`SQLAlchemyError`)
  - JSON parsing fallbacks (`JSONDecodeError`)
  - queue doc-id coercion (`TypeError`, `ValueError`)
  - retry-count coercion (`TypeError`, `ValueError`)
- Reduced remaining `except Exception` sites from **69** to **60**.

### 14. Queue-service exception cleanup

- Continued `2.2 Improve Error Handling` in `backend/app/services/pipeline/queue.py`.
- Replaced the remaining clearly-safe broad catches in queue bookkeeping and lock helpers with concrete Redis/runtime/JSON/coercion exceptions while preserving the existing fail-open behavior used by queue resilience flows.
- Covered:
  - cancel/pause checks
  - worker lock acquire/refresh/release/status
  - running-task read/write helpers
- worker-lock reset fallback
- JSON decoding of queue payload snapshots
- Reduced remaining `except Exception` sites from **60** to **47**.

### 15. Strict mypy expansion across queue and backend regression tests

- Expanded configured strict mypy coverage from **94** to **105** backend source files.
- Added the queue service itself to the strict allowlist:
  - `backend/app/services/pipeline/queue.py`
- Added verified backend regression tests to the strict allowlist:
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
- Added explicit test annotations, type-only fixture imports, and helper typings in the new test batch so strict mypy passes without changing test behavior.
- Fixed a queue-status fallback typing mismatch in `backend/app/routes/queue.py` so the queue service can remain in the strict set.

### 16. Focused exception cleanup in startup, status, sync, and worker bookkeeping

- Continued `2.2 Improve Error Handling` in:
  - `backend/app/main.py`
  - `backend/app/routes/status.py`
  - `backend/app/routes/sync.py`
  - `backend/app/services/integrations/connections.py`
  - `backend/app/worker.py`
- Replaced broad catches with concrete exception classes for:
  - startup meta-cache, tag-sync, and correspondent-sync failures
  - status LLM model fetch failures
  - sync malformed note-id parsing
  - paperless, qdrant, and LLM connection probes
  - worker heartbeat refresh failures
  - worker SQLAlchemy bookkeeping failures
- Reduced remaining `except Exception` sites from **47** to **37**.

### 17. Strict mypy expansion on queue, pipeline, worker-vision, and writeback tests

- Expanded configured strict mypy coverage from **105** to **110** backend source files.
- Added another verified backend regression-test batch to the strict allowlist:
  - `backend/tests/test_queue_resilience.py`
  - `backend/tests/test_queue_stats_self_heal.py`
  - `backend/tests/test_pipeline_similarity_index.py`
  - `backend/tests/test_worker_vision_suggestions.py`
  - `backend/tests/test_writeback_apply_service.py`
- Added explicit fixture/helper annotations and type casts aligned to app types (`Settings`, `Document`) so the new test batch passes strict mypy without behavior changes.

### 18. Focused exception cleanup in writeback, text cleaning, time parsing, and meta cache

- Continued `2.2 Improve Error Handling` in:
  - `backend/app/services/writeback/writeback_apply.py`
  - `backend/app/services/documents/text_cleaning.py`
  - `backend/app/services/runtime/time_utils.py`
  - `backend/app/services/integrations/meta_cache.py`
- Replaced broad catches with concrete exception classes for:
  - writeback integer coercion and Paperless response text parsing
  - invalid note-id parsing in delete paths
  - optional `ftfy` import fallback
  - invalid ISO timestamp parsing
  - meta-cache Paperless refresh failures
- Reduced remaining `except Exception` sites from **37** to **29**.

### 19. Strict mypy expansion on embedding, hierarchical-summary, and fanout tests

- Expanded configured strict mypy coverage from **110** to **113** backend source files.
- Added another verified backend regression-test batch to the strict allowlist:
  - `backend/tests/test_embedding_chunk_budget.py`
  - `backend/tests/test_hierarchical_summary_parsing.py`
  - `backend/tests/test_pipeline_fanout_service.py`
- Added explicit test annotations and app-type casts for settings/document stubs so the new test batch passes strict mypy without behavior changes.

### 20. Focused exception cleanup in writeback dry-run and task-run helpers

- Continued `2.2 Improve Error Handling` in:
  - `backend/app/routes/writeback_dryrun.py`
  - `backend/app/services/pipeline/task_runs.py`
- Replaced broad catches with concrete exception classes for:
  - dry-run doc-id integer coercion
  - dry-run call deserialization validation
  - Paperless reviewed-timestamp refresh failures
  - task-run checkpoint JSON parsing
  - task-run missing-table recovery paths
- Reduced remaining `except Exception` sites from **29** to **24**.

### 21. Strict mypy expansion on evidence and sync/meta route tests

- Expanded configured strict mypy coverage from **113** to **116** backend source files.
- Added another verified backend regression-test batch to the strict allowlist:
  - `backend/tests/test_evidence_service.py`
  - `backend/tests/test_chat_evidence_routes.py`
  - `backend/tests/test_sync_meta_connections_routes.py`
- Added explicit test annotations and a small helper refactor in the sync/meta test so the new batch passes strict mypy without behavior changes.

### 22. Focused exception cleanup in text-page extraction and LLM JSON-mode fallback

- Continued `2.2 Improve Error Handling` in:
  - `backend/app/services/documents/text_pages.py`
  - `backend/app/services/ai/llm_client.py`
- Replaced broad catches with concrete exception classes for:
  - optional `PyMuPDF` / `pdfminer` imports
  - PDF fetch and page-extraction fallback paths
  - selective vision OCR fallback paths
  - JSON-mode retry on OpenAI-compatible chat completion requests
- Reduced remaining `except Exception` sites from **24** to **15**.

### 23. Focused exception cleanup in OCR/suggestion/search helper paths

- Continued `2.2 Improve Error Handling` in:
  - `backend/app/services/ai/ocr_scoring.py`
  - `backend/app/services/ai/suggestions.py`
  - `backend/app/services/search/embeddings.py`
  - `backend/app/services/search/evidence.py`
  - `backend/app/services/pipeline/pipeline_fanout.py`
  - `backend/app/services/ai/vision_ocr.py`
  - `backend/app/services/writeback/writeback_execution.py`
  - `backend/app/services/ai/hierarchical_summary_pipeline.py`
  - `backend/app/worker.py`
- Replaced broad catches with concrete exception classes for:
  - OCR score JSON response parsing
  - suggestions JSON extraction failures
  - embedding overflow and batch-fallback request failures
  - evidence word-match fallback failures
  - pipeline-fanout checkpoint JSON parsing
  - optional vision OCR dependency imports
  - writeback execution runtime/API failures
  - hierarchical section/global summary generation failures
  - worker page-note generation failures
- Reduced remaining `except Exception` sites from **15** to **1**.
- Remaining broad catch is the intentional worker task-dispatch barrier in `backend/app/worker.py`, which is still needed to classify and record arbitrary task failures without crashing the worker loop.

### 24. Strict mypy expansion on queue task-runs and worker checkpoint tests

- Expanded configured strict mypy coverage from **116** to **122** backend source files.
- Added another verified backend regression-test batch to the strict allowlist:
  - `backend/tests/test_large_doc_processing.py`
  - `backend/tests/test_queue_delayed_routes.py`
  - `backend/tests/test_queue_dlq_routes.py`
  - `backend/tests/test_worker_resume_checkpoint.py`
  - `backend/tests/test_worker_retry_checkpoint_sequence.py`
  - `backend/tests/test_queue_task_runs_routes.py`
- Added explicit `-> None` annotations and small typed helper signatures in the queue/worker tests so the new batch passes strict mypy without behavior changes.

### 25. Strict mypy expansion on chat evidence service tests

- Expanded configured strict mypy coverage from **122** to **123** backend source files.
- Added another verified backend regression test to the strict allowlist:
  - `backend/tests/test_chat_service_evidence.py`
- Added explicit monkeypatch/helper annotations and typed casts for citation payload access so the test passes strict mypy without behavior changes.

### 26. Strict mypy expansion on writeback dry-run route tests

- Expanded configured strict mypy coverage from **123** to **124** backend source files.
- Added another verified backend regression test to the strict allowlist:
  - `backend/tests/test_writeback_dryrun_routes.py`
- Tightened local helper typing in the dry-run route regression test and normalized lambda parameter names so the file passes strict mypy and Ruff without behavior changes.

### 27. Strict mypy expansion on remaining backend files

- Expanded configured strict mypy coverage from **124** to **129** backend source files.
- Added the remaining backend files to the strict allowlist:
  - `backend/tests/test_writeback_jobs_routes.py`
  - `backend/tests/conftest.py`
  - `backend/alembic/env.py`
  - `backend/scripts/export_openapi.py`
  - `backend/tests/test_documents_routes.py`
- Tightened helper/fixture annotations across the remaining route and writeback regression tests, normalized the OpenAPI export fallback stubs for type-checking, and kept behavior unchanged while closing the allowlist gap entirely.

### 28. Worker boundary error normalization

- Kept the remaining broad worker dispatch catch in place intentionally, but routed it through `backend/app/exceptions.py` via `WorkerError` instead of leaving it as an unstructured raw exception sink.
- Updated worker error classification to unwrap `WorkerError.original_exception` so retryability and error-code mapping still reflect the real underlying failure.
- Added regression coverage in `backend/tests/test_worker_error_types.py` to verify wrapped worker failures still classify correctly.

### 29. Embeddings route coverage expansion

- Added direct route coverage for `backend/app/routes/embeddings.py` in:
  - `backend/tests/test_embeddings_routes.py`
- Covered queue-backed ingest behavior, queue status reporting, cancel-state persistence, and search result shaping with attached local document context and quality filtering.
- Added the new route test file to the strict mypy allowlist and kept it Ruff-clean.

### 30. Meta and connections coverage expansion

- Added direct route coverage for `backend/app/routes/meta.py` in:
  - `backend/tests/test_meta_routes.py`
- Added unit coverage for `backend/app/services/integrations/connections.py` in:
  - `backend/tests/test_connections_service.py`
- Covered pagination forwarding, stable response-model fields, missing-config branches, HTTP error mapping, and aggregate status formatting for the connection checks.

### 31. Queue route wrapper coverage expansion

- Added direct route coverage for `backend/app/routes/queue.py` in:
  - `backend/tests/test_queue_routes_basic.py`
- Covered disabled/enabled status payloads, enqueue count forwarding, worker-lock status wrapping, and running-task response shaping against the real response models.

### 32. Sync state and queue-route coverage expansion

- Added direct route coverage for `backend/app/routes/sync.py` in:
  - `backend/tests/test_sync_routes_state.py`
- Covered idle sync-status responses, cancel-state persistence, and queued single-document sync with priority/front-of-queue task sequencing.

### 33. Document-actions queue-path coverage expansion

- Added direct route coverage for `backend/app/routes/documents_actions.py` in:
  - `backend/tests/test_documents_actions_routes.py`
- Covered queued cleanup-text task generation and reset-and-reprocess priority enqueue behavior on the enabled queue path.

### 34. Connections route contract coverage

- Added direct route coverage for `backend/app/routes/connections.py` in:
  - `backend/tests/test_connections_routes.py`
- Covered the `/connections/` response contract independently from the service tests so route-level serialization stays pinned to the expected `ConnectionStatus` shape.

### 35. Sync-documents integration coverage expansion

- Added deeper integration coverage for `backend/app/routes/sync.py` in:
  - `backend/tests/test_sync_documents_routes.py`
- Covered the multi-step `/sync/documents` flow for mark-missing plus queued embedding follow-ups, and for `insert_only` behavior that skips existing local rows while inserting new remote rows.

### 36. Process-missing service integration coverage expansion

- Added deeper service coverage for `backend/app/services/pipeline/process_missing.py` in:
  - `backend/tests/test_process_missing_service.py`
- Covered `process_missing_documents()` directly for:
  - `include_sync=True` forwarding with the expected sync flags
  - dry-run selection limiting without enqueue side effects
  - skip behavior for Paperless-tombstoned local documents
  - aggregate preview/missing counters for paperless-embedding gaps
  - enqueue-task sequencing when dry-run is disabled

### 37. Configuration domain split and validation

- Refactored `backend/app/config.py` into validated domain config views while preserving the existing flat `Settings` surface for compatibility with current callers.
- Added focused parsing helpers for booleans, integers, floats, optional strings, and database URL normalization so malformed environment values fail early with clear `ValueError`s.
- Added explicit domain views for:
  - `logging`
  - `api`
  - `worker`
  - `paperless`
  - `database`
  - `qdrant`
  - `queue`
  - `llm`
  - `embeddings`
  - `chunking`
  - `vision`
  - `suggestions`
  - `summary`
  - `http`
  - `ocr_score`
  - `evidence`
  - `writeback`
- Added `backend/tests/test_config.py` to verify the new config views and invalid environment-value validation paths.
- Added the new config regression test to the strict mypy allowlist and kept the compatibility-preserving config refactor fully typed.

### 38. Documents-actions service extraction

- Extracted the pipeline orchestration and cleanup-text execution logic from `backend/app/routes/documents_actions.py` into the new service module `backend/app/services/documents/operations.py`.
- Centralized:
  - pipeline option construction
  - sync freshness checks
  - pipeline status payload building
  - pipeline fanout payload building
  - continue-pipeline enqueue planning
  - cleanup-text execution and queue-path task building
- Reduced `backend/app/routes/documents_actions.py` from `622` lines to `445` lines while keeping the route contracts and existing regression coverage intact.
- Added `backend/app/services/documents/operations.py` to the strict mypy allowlist and kept the extracted service fully typed.

### 39. Low-risk query optimization pass

- Replaced collection `joinedload()` usage with `selectinload()` in hot document and writeback paths to avoid row-multiplying joins on documents with many tags/notes.
- Applied that change in:
  - `backend/app/routes/documents.py`
  - `backend/app/routes/documents_similarity.py`
  - `backend/app/services/search/similarity.py`
  - `backend/app/services/writeback/writeback_preview.py`
  - `backend/app/routes/writeback_dryrun.py`
- Switched the local writeback candidate scans in `backend/app/services/writeback/writeback_preview.py` to `yield_per(500)` so pending writeback discovery can stream over larger tables.
- Kept route/service behavior stable and verified the affected document/similarity/writeback regression suites.

### 40. Tooling and CI enforcement

- Added backend CI in `.github/workflows/backend-ci.yml` to run Ruff, strict mypy, and the full backend pytest suite on backend/tooling changes.
- Updated `.pre-commit-config.yaml` so backend mypy runs through `uv run --project backend` and frontend `oxlint` no longer depends on `bash`.
- Migrated backend dev tooling dependencies in `backend/pyproject.toml` from deprecated `tool.uv.dev-dependencies` to `dependency-groups.dev`.
- Verified the new tooling baseline with backend Ruff, strict mypy, full backend pytest (`221 passed`), pre-commit config validation, YAML validation for the workflow/config files, and a Windows-safe `npx --prefix frontend oxlint --version` sanity check.

### 41. Documents read-model service extraction

- Extracted document list/local-read model shaping out of `backend/app/routes/documents.py` into the new service module:
  - `backend/app/services/documents/read_models.py`
- Centralized:
  - review-status normalization
  - Paperless list pagination/filtering for route consumers
  - derived-field enrichment and summary-preview shaping
  - local override detection
  - local document payload assembly
- Rewired `backend/app/routes/documents_similarity.py` to consume the extracted service helper directly instead of importing a private route helper from `documents.py`.
- Added `backend/app/services/documents/read_models.py` to the strict mypy allowlist and kept the extracted service fully typed.
- Verified with:
  - `cd backend && uv run ruff check app/routes/documents.py app/routes/documents_similarity.py app/services/documents/read_models.py`
  - `cd backend && uv run mypy --config-file pyproject.toml app/routes/documents.py app/routes/documents_similarity.py app/services/documents/read_models.py`
  - `cd backend && uv run mypy --config-file pyproject.toml`
  - `cd backend && uv run pytest tests/test_documents_routes.py tests/test_similarity_service.py tests/test_pipeline_similarity_index.py`

### 42. Sync service extraction

- Extracted document-sync orchestration out of `backend/app/routes/sync.py` into the new service module:
  - `backend/app/services/documents/sync_operations.py`
- Centralized:
  - sync-status payload shaping
  - sync cancellation handling
  - document note merge behavior
  - document upsert behavior
  - multi-document sync execution
  - single-document sync execution
  - embedding execution for synced documents
- Kept route contracts unchanged and preserved the task builder/enqueue injection seam at the route boundary.
- Updated `backend/tests/test_sync_meta_connections_routes.py` so the embedding regression test patches the extracted service seam directly.
- Verified with:
  - `cd backend && uv run ruff check app/routes/sync.py app/services/documents/sync_operations.py tests/test_sync_upsert_notes.py tests/test_sync_routes_state.py tests/test_sync_documents_routes.py tests/test_sync_meta_connections_routes.py`
  - `cd backend && uv run mypy --config-file pyproject.toml app/routes/sync.py app/services/documents/sync_operations.py tests/test_sync_upsert_notes.py tests/test_sync_routes_state.py tests/test_sync_documents_routes.py tests/test_sync_meta_connections_routes.py`
  - `cd backend && uv run mypy --config-file pyproject.toml`
  - `cd backend && uv run pytest tests/test_meta_sync.py tests/test_sync_upsert_notes.py tests/test_sync_routes_state.py tests/test_sync_documents_routes.py tests/test_sync_meta_connections_routes.py`
### 43. Stable API error codes and request-context responses

- Added centralized exception handlers in `backend/app/main.py` for:
  - domain errors (`PaperlessIntelligenceError`)
  - HTTP errors
  - request validation errors
- Error responses now include:
  - `detail`
  - `error_code`
  - `request_id`
  - `correlation_id`
  - `X-Error-Code` response header
- Routed those failures through the structured logging foundation so error responses emit stable status/error-code context in logs.
- Added `backend/tests/test_api_error_responses.py` and brought it into the strict mypy allowlist.

### 44. HTTP client pooling and connection reuse

- Added keyed pooled `httpx.Client` reuse for:
  - `backend/app/services/integrations/paperless.py`
  - `backend/app/services/search/qdrant.py`
  - `backend/app/services/ai/llm_client.py`
- Preserved the existing `with client(...) as http:` call sites by turning those helpers into pooled context managers instead of doing call-site rewrites.
- Added explicit pool-clear and `atexit` cleanup hooks so long-lived processes reuse connections while tests and shutdown stay predictable.
- Added `backend/tests/test_http_client_pooling.py` and brought it into the strict mypy allowlist.

### 45. Embeddings route service extraction

- Extracted embeddings route orchestration out of `backend/app/routes/embeddings.py` into the new service module:
  - `backend/app/services/documents/embedding_operations.py`
- Centralized:
  - queue-backed embeddings enqueue behavior
  - non-queue embeddings ingest execution
  - vector-search result shaping
  - embeddings queue-status payload shaping
  - embeddings cancellation handling
- Kept the route contracts unchanged and preserved the existing route-test monkeypatch seams by injecting the route-level helper functions into the service layer.
- Verified with:
  - `cd backend && uv run ruff check app/routes/embeddings.py app/services/documents/embedding_operations.py tests/test_embeddings_routes.py`
  - `cd backend && uv run mypy --config-file pyproject.toml app/routes/embeddings.py app/services/documents/embedding_operations.py tests/test_embeddings_routes.py`
  - `cd backend && uv run mypy --config-file pyproject.toml`
  - `cd backend && uv run pytest tests/test_embeddings_routes.py tests/test_similarity_service.py tests/test_pipeline_similarity_index.py`

### 46. Worker runtime service extraction

- Extracted worker runtime orchestration out of `backend/app/worker.py` into the new service module:
  - `backend/app/services/pipeline/worker_runtime.py`
- Centralized:
  - queue-payload parsing
  - worker cancel-path handling
  - task dispatch selection
- Kept the actual per-task OCR/embedding/suggestion implementations in `worker.py` for this slice, while moving the queue/runtime control flow into the service layer.
- Added `backend/tests/test_worker_runtime.py` to pin queue-payload parsing, cancel handling, and dispatch routing behavior.
- Verified with:
  - `cd backend && uv run ruff check app/worker.py app/services/pipeline/worker_runtime.py tests/test_worker_runtime.py`
  - `cd backend && uv run mypy --config-file pyproject.toml`
  - `cd backend && uv run pytest tests/test_worker_runtime.py tests/test_worker_error_types.py tests/test_worker_checkpoint_recovery.py tests/test_worker_resume_checkpoint.py tests/test_worker_retry_checkpoint_sequence.py tests/test_worker_vision_suggestions.py`

## Verified commands

```bash
cd backend
uv run mypy --config-file pyproject.toml
uv run ruff check app/routes/connections.py app/routes/meta.py app/services/integrations/paperless.py app/routes/sync.py app/routes/documents_actions.py app/services/writeback/writeback_apply.py app/worker.py
uv run pytest tests/test_sync_meta_connections_routes.py tests/test_status_routes.py tests/test_documents_routes.py
uv run ruff check app/routes/embeddings.py app/services/search/embeddings.py app/services/ai/chat.py
uv run pytest tests/test_chat_routes.py tests/test_chat_service_evidence.py tests/test_embedding_chunk_budget.py
uv run ruff check app/services/writeback/writeback_execution.py app/services/documents/page_text_store.py app/services/ai/suggestion_store.py app/services/pipeline/queue.py app/models.py
uv run pytest tests/test_writeback_jobs_routes.py tests/test_queue_resilience.py tests/test_queue_stats_self_heal.py tests/test_documents_routes.py
uv run ruff check app/services/documents/text_pages.py app/routes/documents.py app/routes/documents_suggestions.py app/services/writeback/writeback_direct.py app/services/pipeline/task_runs.py
uv run ruff check app/routes/chat.py app/routes/documents_common.py app/routes/queue_guard.py app/services/runtime/time_utils.py app/services/runtime/logging_setup.py app/services/search/evidence.py app/routes/documents_similarity.py app/services/integrations/meta_cache.py app/services/integrations/meta_sync.py app/services/search/similarity.py app/services/search/evidence_index.py
uv run pytest tests/test_chat_routes.py tests/test_chat_service_evidence.py tests/test_documents_routes.py
uv run pytest tests/test_sync_meta_connections_routes.py tests/test_chat_service_evidence.py tests/test_documents_routes.py
uv run ruff check app --statistics
uv run ruff check app/routes/queue.py app/routes/writeback_dryrun.py app/services/ai/hierarchical_generation.py app/services/ai/hierarchical_storage.py app/services/ai/hierarchical_summary_pipeline.py
uv run pytest tests/test_writeback_jobs_routes.py tests/test_chat_service_evidence.py tests/test_documents_routes.py
uv run ruff check app/services/ai/llm_client.py app/services/ai/vision_ocr.py app/services/documents/dashboard.py app/services/documents/documents.py app/services/pipeline/process_missing.py app/services/pipeline/sync_state.py
uv run pytest tests/test_chat_service_evidence.py tests/test_documents_routes.py tests/test_queue_resilience.py
uv run ruff check app
uv run mypy --config-file pyproject.toml
uv run pytest tests/test_sync_meta_connections_routes.py tests/test_pipeline_fanout_service.py tests/test_pipeline_similarity_index.py
uv run pytest tests/test_hierarchical_summary_parsing.py tests/test_worker_vision_suggestions.py tests/test_documents_routes.py
uv run ruff check app/services/ai/json_extraction.py app/services/runtime/json_utils.py app/services/runtime/string_list_json.py app/services/writeback/writeback_plan.py app/services/ai/suggestions.py app/services/documents/note_ids.py app/services/pipeline/worker_checkpoint.py
uv run pytest tests/test_hierarchical_summary_parsing.py tests/test_worker_vision_suggestions.py tests/test_documents_routes.py tests/test_writeback_jobs_routes.py
uv run mypy --config-file pyproject.toml app/routes/documents.py app/routes/documents_suggestions.py app/routes/embeddings.py app/services/search/embeddings.py
uv run ruff check app/routes/documents.py app/routes/documents_suggestions.py app/routes/embeddings.py app/services/search/embeddings.py
uv run mypy --config-file pyproject.toml
uv run pytest tests/test_documents_routes.py tests/test_chat_routes.py tests/test_embedding_chunk_budget.py tests/test_chat_service_evidence.py
uv run ruff check app/services/pipeline/queue.py app/services/pipeline/process_missing.py
uv run pytest tests/test_queue_resilience.py tests/test_queue_stats_self_heal.py tests/test_pipeline_fanout_service.py tests/test_pipeline_similarity_index.py
uv run mypy --config-file pyproject.toml app/services/ai/chat.py
uv run ruff check app/services/ai/chat.py app/services/pipeline/queue.py
uv run pytest tests/test_chat_routes.py tests/test_chat_service_evidence.py tests/test_queue_resilience.py tests/test_pipeline_fanout_service.py
uv run mypy --config-file pyproject.toml app/__init__.py app/routes/__init__.py app/services/ai/__init__.py app/services/documents/__init__.py app/services/integrations/__init__.py app/services/pipeline/__init__.py app/services/runtime/__init__.py app/services/search/__init__.py app/services/writeback/__init__.py tests/test_json_utils.py tests/test_note_ids.py tests/test_string_list_json.py tests/test_worker_error_types.py tests/test_worker_checkpoint_recovery.py tests/test_writeback_plan.py tests/test_writeback_selection_service.py
uv run mypy --config-file pyproject.toml
uv run pytest tests/test_json_utils.py tests/test_note_ids.py tests/test_string_list_json.py tests/test_worker_error_types.py tests/test_worker_checkpoint_recovery.py tests/test_writeback_plan.py tests/test_writeback_selection_service.py
uv run ruff check app/routes/documents_actions.py app/worker.py
uv run pytest tests/test_pipeline_fanout_service.py tests/test_pipeline_similarity_index.py tests/test_worker_checkpoint_recovery.py tests/test_worker_error_types.py tests/test_documents_routes.py
uv run ruff check app/services/pipeline/queue.py app/routes/documents_actions.py app/worker.py
uv run pytest tests/test_queue_resilience.py tests/test_queue_stats_self_heal.py tests/test_pipeline_fanout_service.py tests/test_worker_checkpoint_recovery.py tests/test_documents_routes.py
uv run ruff check tests/test_process_missing_service.py
uv run mypy --config-file pyproject.toml tests/test_process_missing_service.py
uv run pytest tests/test_process_missing_service.py
uv run mypy --config-file pyproject.toml
uv run pytest tests/test_embeddings_routes.py tests/test_sync_documents_routes.py tests/test_process_missing_service.py
```

## Current boundary

- The expanded `mypy` allowlist is passing for **46 source files**.
- The expanded `mypy` allowlist is passing for **60 source files**.
- The expanded `mypy` allowlist is passing for **68 source files**.
- The expanded `mypy` allowlist is passing for **72 source files**.
- The expanded `mypy` allowlist is passing for **73 source files**.
- The expanded `mypy` allowlist is passing for **74 source files**.
- The expanded `mypy` allowlist is passing for **78 source files**.
- The expanded `mypy` allowlist is passing for **94 source files**.
- The expanded `mypy` allowlist is passing for **99 source files**.
- The expanded `mypy` allowlist is passing for **105 source files**.
- The expanded `mypy` allowlist is passing for **110 source files**.
- The expanded `mypy` allowlist is passing for **113 source files**.
- The expanded `mypy` allowlist is passing for **116 source files**.
- The expanded `mypy` allowlist is passing for **119 source files**.
- The expanded `mypy` allowlist is passing for **122 source files**.
- The expanded `mypy` allowlist is passing for **123 source files**.
- The expanded `mypy` allowlist is passing for **124 source files**.
- The expanded `mypy` allowlist is passing for **129 source files**.
- The expanded `mypy` allowlist is passing for **130 source files**.
- The expanded `mypy` allowlist is passing for **132 source files**.
- The expanded `mypy` allowlist is passing for **133 source files**.
- The expanded `mypy` allowlist is passing for **134 source files**.
- The expanded `mypy` allowlist is passing for **135 source files**.
- The expanded `mypy` allowlist is passing for **136 source files**.
- The expanded `mypy` allowlist is passing for **137 source files**.
- The expanded `mypy` allowlist is passing for **138 source files**.
- The expanded mypy allowlist is passing for **141 source files**.
- The expanded mypy allowlist is passing for **142 source files**.
- The expanded mypy allowlist is passing for **143 source files**.
- The expanded mypy allowlist is passing for **144 source files**.
- The expanded mypy allowlist is passing for **145 source files**.
- The expanded mypy allowlist is passing for **148 source files**.
- The expanded mypy allowlist is passing for **151 source files**.
- Backend Python files currently present: **129**.
- Strict mypy coverage of backend Python files: **100%** (`151 / 151` configured/tested backend files in the current tree).
- The touched files in this session are Ruff-clean.
- Repo-wide Ruff findings remaining: **0**.
- Remaining `except Exception` sites: **1**.
- The remaining broad catch is the intentional outer worker dispatch boundary, now normalized through `WorkerError` with preserved original error context.
- The last meaningful pre-`2.3` test-coverage slice is now in: thinner route/service wrappers plus deeper sync-documents and process-missing execution paths are covered.
- `2.3 Add Structured Logging` is now implemented in the current branch and verified with focused API/worker logging tests.
- Wider `2.1` coverage is now moving again on top of the structured logging foundation, including direct `process-missing` route coverage and the logging regression tests in the strict mypy set.
- `3.1 Configuration Management` is now in progress with validated domain config views in `backend/app/config.py` and dedicated regression coverage in `backend/tests/test_config.py`.
- `3.3 Service Layer Complexity` is now in progress with the first documents-actions orchestration slice extracted into `backend/app/services/documents/operations.py`.
- `3.2 Database Query Optimization` is now in progress with a first low-risk eager-loading and candidate-scan optimization pass across document/similarity/writeback paths.
- `5.2 Developer Tooling` is now in progress with backend CI, uv-backed pre-commit enforcement, and Windows-safe frontend lint-hook execution.
- `5.3 Error Messages & Observability` is now in progress with stable API error codes and request/correlation context in error responses.
- `6.x Performance & Optimization` is now in progress with a first connection-reuse/client-pooling pass across Paperless, Qdrant, and LLM HTTP clients.
- `3.3 Service Layer Complexity` moved further with a second worker extraction: sync/embedding/evidence/similarity task helpers now live in `backend/app/services/pipeline/worker_document_tasks.py`, leaving `backend/app/worker.py` as a thinner orchestration boundary around the remaining OCR/page-note/suggestion flows.
- `3.2 Database Query Optimization` moved further with composite `task_runs` indexes aligned to the queue history and checkpoint lookup filters (`doc_id`/`task`/`source`/`id`, `status`/`task`/`id`), which is the first DB-focused follow-up after the route/worker SRP cleanup.
- `3.2 Database Query Optimization` moved again with a cheaper `task_runs` pagination path in `backend/app/services/pipeline/task_runs.py`: the service no longer uses a window-count query on every page fetch, and instead derives totals cheaply where possible and falls back to a plain count only when necessary.
- `3.2 Database Query Optimization` moved again in the document list path: `backend/app/services/documents/read_models.py` no longer issues a separate analysis-field lookup per document batch, and instead loads those fields with the main local document query that already hydrates derived list state.
- `3.2 Database Query Optimization` moved again in the same document list path: derived list assembly now skips ordered suggestion-row fetching unless summary previews are requested, and the `vision_ocr` presence flag is driven from distinct doc IDs instead of all matching page rows.
- `3.2 Database Query Optimization` moved into the writeback-preview path: preview assembly now scopes metadata lookups to the correspondent/tag IDs actually referenced by the current preview batch instead of loading the full metadata tables every time.
- `3.2 Database Query Optimization` moved again in the document list path: when summary previews are off, `backend/app/services/documents/read_models.py` now groups suggestion sources per document instead of loading every suggestion row for the current page.
- `3.2 Database Query Optimization` also moved in the dashboard path: `backend/app/services/documents/dashboard.py` now reuses the already-loaded correspondent aggregation rows instead of issuing a second correspondent-name lookup query for the unprocessed breakdown.
- `3.2 Database Query Optimization` moved again in the writeback-preview path: `backend/app/services/writeback/writeback_preview.py` now loads only the local document columns needed for preview assembly, narrows the pending-tag query to the required columns, and scans distinct pending doc IDs instead of walking every pending row during candidate discovery.
- `3.2 Database Query Optimization` moved again in the dashboard path: the grouped correspondent query now also carries per-correspondent unprocessed counts, which removes another dashboard aggregation query without changing the response contract.
- `2.1 Increase Test Coverage` moved again with that SQL slice: `backend/tests/test_documents_routes.py` now includes direct dashboard coverage for grouped correspondent totals and the unprocessed-by-correspondent payload.
- `3.2 Database Query Optimization` moved again in the same dashboard path: document-wide stats, unassigned-unprocessed count, and page-bucket counts now come from one aggregate query instead of multiple full-document scans.
- `2.1 Increase Test Coverage` moved again with that follow-up: the direct dashboard regression now also pins aggregated stats and page-bucket output, not just the correspondent breakdown.
- `3.2 Database Query Optimization` moved again in the document list path: derived-list enrichment now uses one aggregated local-status query for embeddings and `vision_ocr` presence instead of separate list-time scans.
- `3.2 Database Query Optimization` moved again in the single-document path: the local-document payload now uses one aggregated local-status query for embedding state, suggestion-source flags, `vision_ocr` page counts, page-note counts, and review timestamps instead of multiple independent lookups.
- `2.1 Increase Test Coverage` moved again with that follow-up: `backend/tests/test_documents_routes.py` now directly pins the local-document derived processing flags exposed by `/documents/{id}/local`.
- `3.3 Service Layer Complexity` moved further again: worker suggestion-generation, vision-suggestion recovery, and field-variant task handling now live in `backend/app/services/pipeline/worker_suggestion_tasks.py`, with `backend/app/worker.py` reduced to stable wrappers plus the remaining OCR/page-note orchestration.
- `2.1 Increase Test Coverage` also moved with that worker slice: direct worker coverage now includes the `suggest_field` task path in `backend/tests/test_worker_suggest_field.py`.
- `2.1 Increase Test Coverage` moved again to stabilize the remaining inline worker orchestration: `backend/tests/test_worker_doc_orchestration.py` now covers the large-document vision flow inside `_process_doc` plus the early cancel path.
- `3.3 Service Layer Complexity` moved further again: vision OCR, page-note generation, and hierarchical-summary execution now live in `backend/app/services/pipeline/worker_content_tasks.py`, which leaves `backend/app/worker.py` close to its intended role as orchestration plus wrapper seams.
- `3.3 Service Layer Complexity` moved further again: the remaining `_process_doc` full-document flow now lives in `backend/app/services/pipeline/worker_orchestration.py`, which leaves `backend/app/worker.py` essentially as runtime loop, dispatch wiring, and test-friendly wrappers.
- CI and release hygiene were re-verified again on top of current `develop`: the full backend CI equivalent passes locally (`ruff`, `mypy`, `pytest`), the frontend CI equivalent also passes locally (`lint`, `type-check`, `test:coverage`, `build`), `backend/scripts/export_openapi.py` still exports successfully, and the scripted version bump path has now advanced the repo to `0.4.8`.
- `5.1 API Documentation` is now in progress: the public document and writeback route/service seams have focused docstrings covering review-status filtering, derived local payload assembly, dashboard aggregation, and writeback preview/job behavior.
- CI and release hygiene were re-verified again on top of current `develop`: the full backend CI equivalent still passes locally (`ruff`, `mypy`, `pytest`), the frontend CI equivalent still passes locally (`lint`, `type-check`, `test:coverage`, `build`), `backend/scripts/export_openapi.py` still exports successfully, and the scripted version bump path has now advanced the repo to `0.4.9`.
- `5.1 API Documentation` moved further: the public sync, embeddings, and worker orchestration/runtime seams now also have focused docstrings covering sync-state semantics, queue-vs-inline embedding behavior, and the worker dispatch/orchestration contract.
- CI and release hygiene were re-verified again on top of current `develop`: the full backend CI equivalent still passes locally (`ruff`, `mypy`, `pytest`), the frontend CI equivalent still passes locally (`lint`, `type-check`, `test:coverage`, `build`), `backend/scripts/export_openapi.py` still exports successfully, and the scripted version bump path has now advanced the repo to `0.4.10`.
- `5.1 API Documentation` is now complete for the current stable backend seams: chat, documents, sync, embeddings, queue, status, writeback, task-run, logging, and worker orchestration/runtime surfaces all have focused docstrings that explain the route/service contracts rather than just restating code.
- CI and release hygiene were re-verified again on top of current `develop`: the full backend CI equivalent still passes locally (`ruff`, `mypy`, `pytest`), the frontend CI equivalent still passes locally (`lint`, `type-check`, `test:coverage`, `build`), `backend/scripts/export_openapi.py` still exports successfully, and the scripted version bump path has now advanced the repo to `0.4.11`.
- `3.4 Reduce Import Complexity` is now in progress: vector search/storage operations are routed through a new adapter seam in `backend/app/services/search/vector_store.py`, which removes direct Qdrant knowledge from higher-level services like guard, connections, similarity, embedding-init, and route/service orchestration code.
- `7. Vector Store Migration Prep` is now in progress: the current Qdrant behavior lives behind a provider-shaped adapter module, generic `VECTOR_STORE_*` settings now exist alongside legacy `QDRANT_*` compatibility, and the next provider switch can target a Weaviate adapter without another repo-wide call-site rewrite.
- CI and release hygiene were re-verified again on top of current `develop`: the full backend CI equivalent still passes locally (`ruff`, `mypy`, `pytest`), the frontend CI equivalent still passes locally (`lint`, `type-check`, `test:coverage`, `build`), `backend/scripts/export_openapi.py` still exports successfully, and the scripted version bump path has now advanced the repo to `0.4.12`.
- `3.4 Reduce Import Complexity` moved further: the vector-store seam now has two real provider layers, so higher-level code no longer needs to know whether it is operating against Qdrant or Weaviate.
- `7. Vector Store Migration Prep` has moved from prep into implementation: Weaviate support now exists behind the adapter boundary, uses the official `weaviate-client`, supports separate HTTP and gRPC connection settings, and stores centroid/doc-similarity vectors in a separate collection from chunk vectors.
- CI and release hygiene were re-verified again on top of current `develop`: the full backend CI equivalent still passes locally (`ruff`, `mypy`, `pytest`), the frontend CI equivalent still passes locally (`lint`, `type-check`, `test:coverage`, `build`), `backend/scripts/export_openapi.py` still exports successfully, and the feature bump has now advanced the repo to `0.5.0`.
- `3.4 Reduce Import Complexity` moved further again: [`backend/app/routes/documents_actions.py`](E:/workspace/python/paperless-intelligence/backend/app/routes/documents_actions.py) no longer imports sync helpers from another route module and now calls the extracted sync service seam directly, which removes one of the remaining route-to-route dependencies left after the earlier SRP work.
- CI and release hygiene were re-verified again on top of current `develop`: the full backend CI equivalent still passes locally (`ruff`, `mypy`, `pytest`), the frontend CI equivalent still passes locally (`lint`, `type-check`, `test:coverage`, `build`), `cd backend && uv run python scripts/export_openapi.py` still exports successfully, and the scripted version bump path has now advanced the repo to `0.5.1`.
- `2.1 Increase Test Coverage` moved further again: the real Weaviate adapter behavior now has direct regression coverage for collection creation, chunk-vs-centroid upsert routing, centroid-search selection, and chunk-to-centroid retrieve fallback in [`backend/tests/test_weaviate_adapter.py`](E:/workspace/python/paperless-intelligence/backend/tests/test_weaviate_adapter.py), which closes the biggest remaining test gap from the `0.5.0` vector-store feature block.
- CI and release hygiene were re-verified again on top of current `develop`: the full backend CI equivalent still passes locally (`ruff`, `mypy`, `pytest`), the frontend CI equivalent still passes locally (`lint`, `type-check`, `test:coverage`, `build`), `cd backend && uv run python scripts/export_openapi.py` still exports successfully, and the scripted version bump path has now advanced the repo to `0.5.2`.
- `6.2 Caching Strategy` is now in progress: the document dashboard cache has been extracted into [`backend/app/services/documents/dashboard_cache.py`](E:/workspace/python/paperless-intelligence/backend/app/services/documents/dashboard_cache.py) and is now explicitly invalidated by sync and document-mutation routes instead of relying only on the short TTL window.
- `2.1 Increase Test Coverage` moved again alongside that cache work: [`backend/tests/test_documents_routes.py`](E:/workspace/python/paperless-intelligence/backend/tests/test_documents_routes.py) now pins that a cached dashboard payload is invalidated after suggestion deletion, so the operations view sees fresh aggregate counts immediately after a mutating action.
- CI and release hygiene were re-verified again on top of current `develop`: the full backend CI equivalent still passes locally (`ruff`, `mypy`, `pytest`), the frontend CI equivalent still passes locally (`lint`, `type-check`, `test:coverage`, `build`), `cd backend && uv run python scripts/export_openapi.py` still exports successfully, and the scripted version bump path has now advanced the repo to `0.5.3`.
- `6.1 Async/Await Optimization` is now effectively complete for the low-risk backend pass: the blocking `/status/stream` payload build in [`backend/app/routes/status.py`](E:/workspace/python/paperless-intelligence/backend/app/routes/status.py) now runs through `asyncio.to_thread(...)`, so the SSE loop no longer performs DB/HTTP work directly on the event loop.
- `2.1 Increase Test Coverage` moved again alongside that async fix: [`backend/tests/test_status_routes.py`](E:/workspace/python/paperless-intelligence/backend/tests/test_status_routes.py) now directly asserts that `/status/stream` offloads the blocking payload build, and [`backend/tests/test_chat_evidence_routes.py`](E:/workspace/python/paperless-intelligence/backend/tests/test_chat_evidence_routes.py) was hardened to stop depending on real PDF/network behavior during route tests.
- `6.2 Caching Strategy` moved further: [`backend/app/services/documents/document_stats_cache.py`](E:/workspace/python/paperless-intelligence/backend/app/services/documents/document_stats_cache.py) now caches the `/documents/stats` aggregate payload, [`backend/app/routes/status.py`](E:/workspace/python/paperless-intelligence/backend/app/routes/status.py) reuses that cached stats snapshot inside `/status/stream`, and the document-stats cache is now explicitly invalidated by sync and document-mutation routes alongside the existing dashboard cache.
- `2.1 Increase Test Coverage` moved again with that cache follow-up: [`backend/tests/test_documents_routes.py`](E:/workspace/python/paperless-intelligence/backend/tests/test_documents_routes.py) now pins that `/documents/stats` invalidates immediately after suggestion deletion instead of serving stale counts until TTL expiry.
- CI and release hygiene were re-verified again on top of current `develop`: the full backend CI equivalent still passes locally (`ruff`, `mypy`, `pytest`), the frontend CI equivalent still passes locally (`lint`, `type-check`, `test:coverage`, `build`), `cd backend && uv run python scripts/export_openapi.py` still exports successfully, and the scripted version bump path has now advanced the repo to `0.5.9`.
- `6.2 Caching Strategy` moved further again: [`backend/app/services/writeback/writeback_preview_cache.py`](E:/workspace/python/paperless-intelligence/backend/app/services/writeback/writeback_preview_cache.py) now caches `only_changed` writeback candidate discovery and preview payloads by doc-id selection, and [`backend/app/routes/writeback_dryrun.py`](E:/workspace/python/paperless-intelligence/backend/app/routes/writeback_dryrun.py) now reuses those cached payloads across preview, execute-now, dry-run-execute, and writeback-job creation paths.
- `6.2 Caching Strategy` also now has explicit writeback invalidation: the preview cache is cleared when direct writeback, execute-now, queued job execution, or execute-pending flows mutate pending rows or writeback audit state, so the cache reduces repeated preview work without serving stale writeback candidates after execution.
- `2.1 Increase Test Coverage` moved again with that cache slice: [`backend/tests/test_writeback_preview_service.py`](E:/workspace/python/paperless-intelligence/backend/tests/test_writeback_preview_service.py) now directly proves cached candidate/preview payloads remain hot until invalidated and then refresh to the new writeback state.
- CI and release hygiene were re-verified again on top of current `develop`: the full backend CI equivalent still passes locally (`ruff`, `mypy`, `pytest`), the frontend CI equivalent still passes locally (`lint`, `type-check`, `test:coverage`, `build`), `cd backend && uv run python scripts/export_openapi.py` still exports successfully, and the scripted version bump path has now advanced the repo to `0.5.10`.
- `6.2 Caching Strategy` moved further again: [`backend/app/services/documents/documents_list_cache.py`](E:/workspace/python/paperless-intelligence/backend/app/services/documents/documents_list_cache.py) now caches the expensive locally-enriched `/documents` pages by request parameters whenever derived state or review-status filtering is involved, instead of rebuilding those overlays on every identical view refresh.
- `6.2 Caching Strategy` now also has explicit derived-list invalidation: document review, sync, document mutation, and writeback execution paths clear the documents-list cache so derived pages refresh immediately after local review status, pending metadata, or writeback state changes.
- `2.1 Increase Test Coverage` moved again with that cache slice: [`backend/tests/test_documents_routes.py`](E:/workspace/python/paperless-intelligence/backend/tests/test_documents_routes.py) now proves the cached unreviewed documents page invalidates after `POST /documents/{id}/review/mark`, and [`backend/tests/conftest.py`](E:/workspace/python/paperless-intelligence/backend/tests/conftest.py) now resets the in-memory caches between tests so the new cache layers stay isolated in the backend suite.
- CI and release hygiene were re-verified again on top of current `develop`: the full backend CI equivalent still passes locally (`ruff`, `mypy`, `pytest`), the frontend CI equivalent still passes locally (`lint`, `type-check`, `test:coverage`, `build`), `cd backend && uv run python scripts/export_openapi.py` still exports successfully, and the scripted version bump path has now advanced the repo to `0.5.11`.
