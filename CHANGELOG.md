# Changelog

All granular implementation slices and refactors are tracked here.
`agents.md` keeps only high-level project state.

## 2026-02-20 (branch: codex-20260220-backend-principles-pass)

### Backend robustness / SRP-DRY-KISS cleanup
- `fa56888` fix(sync): fixed non-queue embedding sync path by importing and using `embed_text` in `app/routes/sync.py` (`_embed_documents` no longer raises `NameError` when `embed=true` and queue is disabled).
- `fa56888` refactor(writeback): extracted shared writeback field-selection helpers in `app/routes/writeback_dryrun.py` (`_collect_local_selection`, `_normalize_changed_field`, `_cleanup_pending_rows_after_patch`) and reused them across dry-run and execute-direct flows to reduce duplicated payload/call assembly logic.
- `fa56888` refactor(writeback): split execute-direct concerns with dedicated helpers (`_build_writeback_conflicts`, `_resolve_direct_selection`, `_execute_direct_selection`) to keep endpoint orchestration thin and improve SRP.
- `9675ff4` refactor(documents-actions): extracted `/documents/process-missing` orchestration into `app/services/process_missing.py` (`ProcessMissingOptions`, `process_missing_documents`) and reduced route-layer complexity in `app/routes/documents_actions.py`.
- `9675ff4` refactor(time-utils): added shared `utc_now_iso()` in `app/services/time_utils.py` and replaced repeated local timestamp helpers in `writeback_dryrun`, `documents_suggestions`, `hierarchical_summary`, `ocr_scoring`, and `task_runs`.
- `c6c0017` fix(api-wiring): mounted `connections` router in `app/main.py` (`/api/connections`) so the existing endpoint is reachable.

### Tests
- `c6c0017` test(sync/meta/connections): added `backend/tests/test_sync_meta_connections_routes.py` with route coverage for `/sync/tags`, `/sync/correspondents`, `/sync/document-types`, `/tags`, `/correspondents`, `/document-types/{id}`, and `/connections/`.
- `c6c0017` test(sync-embed-regression): added regression test ensuring `_embed_documents` exercises `embed_text` path in non-queue mode and persists embedding metadata.

## 2026-02-20 (branch: codex-20260220-frontend-polish-pass)

### Frontend robustness / high+medium polish
- `8222068` fix(lint): resolved frontend lint blockers by removing unused vars/imports and replacing prop mutation in `ContinueProcessingPanel` with explicit update events (`update:includeSync`, `update:strategy`) handled by `ContinueProcessingView`.
- `8222068` test(frontend): added Vitest baseline (`frontend/vitest.config.ts`, `test`/`test:run` scripts, `vitest` devDependency) with utility coverage for `queryState`, `number`, and `writebackPreview`.
- `8222068` perf(frontend): reduced initial JS payload and removed large-chunk build warning by converting route view imports in `frontend/src/main.ts` to lazy-loaded dynamic imports.
- `8222068` refactor(frontend): extracted continue-processing preview prioritization/strategy logic into `frontend/src/utils/continueProcessingPanel.ts` to reduce component coupling and improve DRY/SRP.
- `199eb7d` refactor(frontend): reduced god-file pressure by extracting `QueueView` and `DocumentDetailView` formatting/state helpers into `frontend/src/utils/queueView.ts` and `frontend/src/utils/documentDetail.ts`, plus reusable maintenance action UI into `frontend/src/components/MaintenanceActionCard.vue`.
- `2ce80fc` test(frontend): expanded frontend coverage with composable tests, `ContinueProcessingPanel` integration test, queue/detail utility tests, and Playwright smoke tests (`frontend/e2e/smoke.spec.ts` + `frontend/playwright.smoke.config.ts`).
- `efead80` ci(frontend): added `.github/workflows/frontend-ci.yml` to gate frontend changes on lint, type-check, unit/integration tests, build, and optional smoke e2e execution via `RUN_E2E_SMOKE`.
- `a1dc08f` refactor(frontend): continued medium SRP cleanup by extracting document operations/timeline derived state into `frontend/src/composables/useDocumentProcessingState.ts` and runtime config row rendering into `frontend/src/components/MaintenanceRuntimeRow.vue`, reducing `DocumentDetailView` + `MaintenanceView` inline complexity.
- `8aefb53` test(ci): added `useDocumentProcessingState` test coverage and Vitest coverage guardrails (`frontend/vitest.config.ts`, `npm run test:coverage`) over core composables/utils; updated frontend CI smoke gating to run by default unless explicitly disabled (`RUN_E2E_SMOKE=0`) so smoke e2e is enforced even when repo variables are missing.
- `dd4b7a7` refactor(frontend): extracted the entire Document Details Operations tab into dedicated `frontend/src/components/DocumentOperationsSection.vue`, reducing `DocumentDetailView` template size/coupling and keeping route-level orchestration in the view.
- `53c46e4` test(ci): added `frontend/src/views/MaintenanceView.integration.test.ts` to validate runtime-row copy wiring, switched frontend CI test step to coverage-gated execution (`npm run test:coverage`), and raised core frontend coverage thresholds (`lines/statements/functions: 75`, `branches: 60`).
- `141d0ac` refactor(frontend): moved writeback conflict modal UI into `frontend/src/components/WritebackConflictModal.vue` and extracted writeback state/handlers into `frontend/src/composables/useDocumentWriteback.ts`, reducing `DocumentDetailView` coupling in the writeback path.
- `a48bed7` test(ci): added `frontend/src/components/DocumentOperationsSection.integration.test.ts` for operations-tab event wiring and `frontend/src/utils/continueProcessingPanel.test.ts` for priority/strategy branch coverage, added backend-connected smoke CI job on `:8001` in `.github/workflows/frontend-ci.yml`, and raised core coverage thresholds to `lines/statements/functions: 80`, `branches: 65`.

## 2026-02-18 (branch: fix/pending-correspondent-suggestions)

### Suggestions / writeback robustness
- `8d88da7` feat(suggestions/writeback): unknown correspondent suggestions are now persisted locally as pending correspondent values (new table `document_pending_correspondents`) instead of being dropped. Document list/detail now surfaces pending correspondent names, local override/review-state detection includes pending correspondent changes, and writeback resolves/creates correspondents in Paperless (similar to pending tags) before PATCH so `Save` + writeback works end-to-end for new correspondents.
- `bacfc8c` fix(writeback): when a pending correspondent is resolved/created during writeback, the resolved correspondent id is now written back to the local document as well (and pending row cleared), preventing the UI from showing an unset correspondent after successful writeback. Added regression test coverage for id normalization (`\"77\" -> 77`) and local persistence.
- `1100be7` fix(writeback): hardened execute-direct PATCH payload assembly to prevent invalid null fields (`created=None`, `correspondent=None`) from being sent to Paperless. Correspondent resolution now fails fast with a clear error if pending correspondent creation cannot be resolved, and empty PATCH payloads are skipped. Added regression test for doc flow mirroring real `POST /writeback/documents/{id}/execute-direct` behavior.
- `5c66469` fix(writeback): `execute-direct` now converts Paperless PATCH 4xx failures into actionable API errors (`HTTP 400`) including sanitized payload + response snippet, and retries once without `created` when Paperless rejects date/null combinations. This removes opaque `500` traces and makes remaining invalid-field cases diagnosable from the UI/API response directly.
- `474d4f1` fix(writeback): stale local correspondent IDs are now validated against Paperless on resolve. If local ID no longer exists remotely, writeback resolves by correspondent name (existing or newly created in Paperless), remaps local document references from stale ID to the resolved ID, and keeps the stale local correspondent cache row (no hard delete). Added regression test covering stale-id remap across multiple local documents.
- `f1ff055` fix(writeback): fixed local FK remap ordering for stale correspondent migration. The target correspondent row is now upserted and flushed before bulk-updating `documents.correspondent_id`, preventing PostgreSQL foreign-key violations (`documents_correspondent_id_fkey`) during execute-direct remaps.

## 2026-02-14 (performance branch: perf/ops-route-speedups)

### Backend performance
- `fd5ba5f` docs(handover): updated `README.md` and `agents.md` with today's operational behavior fixes (writeback preview candidate logic, sync-after-writeback consistency, summary-only suggestion regeneration, suggestions inline-variant UX) for next-session continuity.
- `dc83879` ux(suggestions): moved field variants inline under each suggestion field (title/date/correspondent/tags) to match summary UX, added visual separators between summary variants, and removed legacy `Existing tags / New tags` debug hint boxes from suggestion panels.
- `215dfd3` feat(suggestions): added summary-only suggestion regeneration via `field=note` variants. Backend now supports note-summary field prompts (`suggestions_summary.txt`), maps note field updates to `summary` payload storage, and frontend Suggestions panels now expose `Suggest new` for summary plus inline summary variant apply actions. Added route tests for current-summary reuse and summary update mapping.
- `96dd3a4` fix(writeback): `dry-run/preview` now uses local writeback candidates (`suggestion_audit` apply actions + pending-tag docs) when `only_changed=true`, instead of relying only on page-1 Paperless listing; this fixes missing changed documents in Writeback Preview after bulk suggestion-apply workflows. Added route regression test coverage.
- `874850a` fix(details/ui): fixed Vue template compile error in `DocumentDetailView` by replacing invalid double `v-else` chains (fan-out and timeline mobile/desktop blocks) with `v-else` wrapper templates.
- `4861a2c` fix(writeback/sync): fixed false `Sync: Missing` after successful writeback by avoiding stale Paperless reads (`_reviewed_timestamp_for_doc` now fetches uncached document), and by invalidating Paperless doc/list caches after document patch/note add/note delete operations; added regression coverage in `test_writeback_dryrun_routes.py`.
- `333598d` perf(dashboard): reduced dashboard query load by deriving unknown correspondent/type counts from total docs and grouped rows, and replacing correlated untagged-doc counting with a single `count(distinct document_tags.document_id)` query.
- `39a28a3` docs(todo): marked the remaining responsive/mobile polish backlog item as completed after recent `Writeback` and `DocumentDetail` narrow-screen improvements.
- `3999fc8` ux(details): improved `DocumentDetailView` operations responsiveness by adding mobile card layouts for processing timeline and downstream fan-out, plus wrapped controls for narrow screens.
- `d3de19f` ux(writeback): improved `WritebackDryRunView` responsiveness with mobile-friendly tab scrolling, stacked preview field cards on small screens, wrapped action toolbars, and card-based queue/history rendering on phones while preserving desktop tables.
- `24f31bd` fix(documents/ui): fixed `DocumentsTable.vue` template structure by replacing invalid double `v-else` chain with a single `v-else` wrapper template for mobile+desktop non-card layouts (resolves Vite compile error “v-else has no adjacent v-if”).
- `1e9b35b` ux(task-runs): enabled Vue Query `keepPreviousData` in `useDocumentTaskRuns` to prevent task-run list flicker in document-detail run inspector filters.
- `6681bf4` ux(queue): added a compact “Recent task runs” timeline card in `QueueView` (latest runs with status, error type, duration, timestamp) for faster worker triage without navigating the full history table.
- `b4a1c75` ux(task-runs): enabled Vue Query `keepPreviousData` in `useTaskRunInspector` so paginated/filter changes keep previous rows visible until refreshed data arrives.
- `dd157b4` refactor(writeback/json): extended `json_utils` with `parse_json_list` and reused it in writeback job deserialization (`doc_ids_json`, `calls_json`) to reduce duplicated JSON error handling and make partial-bad payloads more tolerant.
- `739bd91` observability(api): added configurable slow-request logging middleware on `/api` routes (`API_SLOW_REQUEST_LOG_MS`) with method/path/status/duration output, reused a single module-level settings instance in `main.py`, and documented the new env var in `.env.example` and `.env.worker.example`.
- `deb425a` docs(todo): refreshed `docs/TODO.md` with compact post-QA backlog items (responsive polish, endpoint timing observability, compact worker timeline UX).
- `517ebad` ux(writeback): enabled Vue Query `keepPreviousData` for writeback preview/jobs/history queries to reduce list flicker during reloads and query transitions.
- `517ebad` fix(documents): made suggestions query ordering deterministic in `/documents` (`doc_id`, `source`) to keep summary-preview source selection stable across DB/plans.
- `b4a024d` ux(queue): enabled Vue Query `keepPreviousData` for queue list queries (`peek`, `task-runs`, `delayed`, `dlq`) to reduce UI flicker while changing limits/filters.
- `eaf3863` perf(documents): reduced suggestion lookup overhead in `/documents` by reusing one suggestion query for source flags + optional summary preview extraction, and replaced duplicated suggestion-payload JSON parsing in `documents_suggestions` with shared `parse_json_object`.
- `cd10d37` ux(documents): enabled Vue Query `keepPreviousData` for the documents list query to avoid table/card flicker while changing pagination and filters.
- `1d4caaa` refactor(json): added shared JSON object parser `app/services/json_utils.py` and reused it across documents/suggestions code paths (`documents`, `documents_common`, `suggestion_store`) to reduce duplicated parsing/error handling; added focused helper tests.
- `da68f7d` test(helpers): added focused tests for `string_list_json` and `note_ids` helpers, and made `normalize_string_list` ordering deterministic (`(lowercase, original)`) to avoid unstable output ordering.
- `121425e` refactor(json-lists): extracted shared string-list JSON helpers (`parse`, `normalize`, `dump`) to `app/services/string_list_json.py` and reused them for pending-tag handling in `documents`, `documents_suggestions`, and `writeback_dryrun`.
- `776ebd9` refactor(notes): extracted shared local-note id allocator to `app/services/note_ids.py` and removed duplicated `_next_local_note_id` implementations from `sync`, `documents_suggestions`, and `writeback_dryrun`.
- `cba3f38` refactor(frontend/queue-types): replaced manual `QueueErrorTypeDetail` shape with alias to generated OpenAPI type `ErrorTypeDetail` to reduce duplicate type maintenance.
- `b1428bc` fix(documents-list): resolved variable-shadowing regression in summary preview extraction (`payload` overwrite) and added route test coverage for `include_summary_preview` behavior (preview absent by default, present when requested).
- `e8c80a5` perf(documents-list): added optional `include_summary_preview` query parameter to `/documents` and wired UI to request summary previews only in card view; this avoids loading/parsing suggestion payloads on normal table view while preserving card preview behavior.
- `a4509e2` refactor(frontend/http): removed unused generic `request` transport helpers from `services/http.ts` and kept only `ApiError`, since all active service calls now use generated OpenAPI clients + `unwrap`.
- `f4e7319` refactor(frontend/queue-api): migrated queue utility calls (`running`, `worker-lock`, `worker-lock/reset`, `error-types`) from custom `request` helper to generated OpenAPI client endpoints; aligned exported queue response types with generated models.
- `844320b` refactor(frontend/documents-api): switched document operations/pipeline calls (`cleanup-texts`, `enqueue-task`, `reset-and-reprocess`, `pipeline-status`, `pipeline/continue`) from custom `request` wrappers to generated OpenAPI client functions; preserved strict UI typing via explicit task union + normalized cleanup result mapping.
- `c7e4c9c` refactor(documents): extracted shared helpers for pending-tag parsing and local-override evaluation to remove duplicated list/detail logic (DRY/SRP), and reduced `/documents/{id}/local` DB roundtrips by aggregating page-note counts in a single grouped query.
- `7bbed1f` refactor(frontend/writeback): replaced custom HTTP delete call with generated OpenAPI client (`deleteWritebackJobWritebackJobsJobIdDelete`) in `services/writeback.ts`, keeping writeback API access fully contract-driven.
- `0baac9b` fix(documents): hardened local-override detection for nullable/empty scalar fields (`title`, `document_date/created`, `correspondent`) so intentional clears are recognized consistently in list + local detail review state; also guarded OCR score JSON decoding against malformed payloads in `/documents/{id}/ocr-scores` and added regression tests.
- `30bbb7f` feat(documents/mobile): added dedicated small-screen fallback list for table mode in `DocumentsTable` (title/date/correspondent/status/actions), while keeping the full table on `md+`; this removes horizontal cut-off pain on phones without changing desktop behavior.
- `1bfa215` chore(api): regenerated OpenAPI spec + Orval client/models after recent backend route additions (`writebackJobDeleteResponse` now in generated frontend models), then revalidated with frontend type-check and backend compileall.
- `958647a` perf(writeback): reduced dry-run preview latency on larger selections by adding batched/parallel remote document fetch (`paperless.get_documents_cached`) and switching preview page list fetches to cached list calls.
- `8ba4627` docs(todo): updated `docs/TODO.md` to reflect completed QA findings from the latest UX/flow validation pass and left only remaining backlog items (writeback preview performance optimization).
- `f86e8c0` feat(documents/ui): card view now shows an AI summary preview (derived from stored suggestion payload summaries) to add context/value beyond status badges.
- `20a3d96` refactor(documents/ui): removed duplicate review-state controls from the sticky quick bar so review filtering is driven by the Presets section only, reducing Triage/Preset overlap.
- `f59032d` feat(dashboard/ui): top dashboard lists are now padded to always render 10 rows for consistent scanability (even on smaller datasets).
- `68d2427` fix(pages): document page-text endpoint now prefers `clean_text` for vision OCR rows (fallback to raw text), so Details > Pages shows normalized vision text instead of noisy raw output when cleanup exists.
- `b62e9e0` feat(dashboard): updated dashboard aggregations/UI to use top-10 lists, split page-count bucket `51+` into `51-99` and `100+`, show ratio percentages alongside counts, add tag donut tooltip details, and improve extended-section narrow-screen stability with `min-w-0` + scrollable card content.
- `7eafc2f` feat(writeback/documents): added removable writeback queue items (`DELETE /writeback/jobs/{id}` + UI remove action for pending jobs) and introduced documents filter option “Without correspondent” (UI `-1` sentinel + backend filtering for `correspondent is null`, including review-status paths).
- `65de851` refactor(writeback/ui): removed the redundant “Run dry-run now” action from Writeback Preview so execution flows consistently through queued jobs.
- `e26c57a` feat(documents/ui): pagination now hides `Prev` on first page and `Next` on last page, and page-jump input clamps on blur to prevent lingering out-of-range page values.
- `bc19623` fix(suggestions/ui): hardened suggestion field rows for long values by applying `min-w-0`/`break-words` wrapping and aligning action groups to top, preventing long “Current” text from pushing `Suggest new`/`Save` controls out of reach.
- `792cf90` fix(details): AI summary-note metadata now formats `Created` timestamps in compact human-readable form (`YYYY-MM-DD HH:MM:SS`) instead of raw ISO with timezone/microseconds.
- `b0ed4f0` feat(logs/ui): improved Log Inspector UX by replacing free-text error-type input with catalog-backed dropdown, removing the full-text query control, mapping quick overflow filter to `EMBED_CONTEXT_OVERFLOW`, and increasing padding in the error-type reference panel.
- `46b3ea4` fix(chat/docs): fixed streaming chat URL construction in `useChatSession` to avoid double `/api` prefixes (resolves `POST /api/api/chat/stream` 404), and added `docs/TODO.md` as central backlog capturing QA findings from live test runs.
- `6483823` refactor(backend): replaced deprecated FastAPI `@on_event(\"startup\")` usage with lifespan-based startup hook while preserving startup cache/meta sync behavior; this removes recurring deprecation noise in tests/runtime.
- `2dbd317` test(task-runs): added regression coverage for task-runs pagination totals (normal paged result and empty-page offset) to protect the new single-query/window-count list behavior.
- `90674f0` chore(api): synchronized `backend/openapi.json` and frontend generated OpenAPI client/models (including queue error-type and evidence resolver models) to keep frontend contracts aligned with the latest backend API surface.
- `55ae5df` perf(backend): removed redundant `count()+delete()` query pairs in document cleanup delete endpoints by using delete rowcounts directly, reducing DB round-trips on maintenance operations.
- `c99036e` perf(backend): improved document list hot path by loading only required `Document`/relationship columns for derived review-state computation (avoids pulling full `content` blobs), optimized task-run pagination to use window-count in the main query (single-query fast path), and hardened queue task-run serialization to skip/log malformed rows instead of failing the whole endpoint.
- `7815175` refactor(backend): simplified `documents_actions` by removing redundant local wrapper helpers around pipeline planner APIs and using shared service functions/types directly (same behavior, lower indirection).
- `bf829d3` perf(backend): reduced `documents_actions` hot-path overhead by streaming latest task-run lookups (early break on required signatures), streaming global cleanup doc-id scans, and removing dead helper code to keep the route module leaner.
- `904d54d` perf(backend): reduced memory pressure in pipeline planning by streaming cache source queries via `yield_per(500)` (embeddings/suggestions/vision/page-notes/anchors) and slimmed writeback dry-run metadata map loading to `id/name` projections instead of full ORM rows.
- `0b1e65e` refactor(backend): extracted dashboard aggregation into `app/services/dashboard.py` to slim `documents` routes and improve SRP, and switched pending writeback execution iteration to `yield_per(50)` to reduce memory pressure on large pending queues.
- `aaae285` perf(backend): reduced memory/latency overhead in pipeline routes by narrowing cache queries to required columns/doc scopes, optimized task-run fanout lookups to planned signatures, and consolidated document stats calculation into a single aggregate query shared by `/documents/stats` and status stream payloads.
- `0638a6e` perf(backend): improved route hot paths and backend hygiene by streaming review-status document filtering, making process-missing sync incremental + lower-memory iteration, removing write-on-read behavior from `/status`, adding short-TTL Paperless/dashboard caching for expensive reads, extracting shared review/sync derivation helpers, and replacing remaining `__import__` anti-patterns in core backend modules.
- `8ea99eb` perf(backend): removed document-list derived-field N+1 risks with eager loading and slimmer projections, switched `process-missing` to chunked cache evaluation (no global pre-scan cache load), added shared SSE payload caching in `/status/stream` to reduce per-client DB/LLM pressure, reduced embeddings ingest memory by tracking counts instead of storing all points in-route, and deduplicated writeback metadata-map loading while using cached Paperless document reads in preview/execute flows.
- `6554848` refactor(ux+backend): improved mobile/responsive behavior for documents + continue-processing views/components and extracted pipeline planning/evaluation/cache logic from `documents_actions` into `app/services/pipeline_planner.py` to reduce route-module coupling and improve SRP.

## 2026-02-14 (documentation branch: docs/concise-manual)

### Documentation
- `e4e39c7` docs(manual): rewrote `MANUAL.md` into a concise operator/user guide covering local run flows (backend/worker/frontend), Alembic, Docker variants, page-by-page usage, processing flow, and troubleshooting.

## 2026-02-14 (current branch: feat/documents-triage-presets-search)

### Documentation / governance
- `1dbf86e` docs: compacted `README.md`/`agents.md` and moved granular history into `CHANGELOG.md`.
- `2a2f2e5` docs(agents): require changelog entries with git hashes when available.
- `5506b30` docs(agents): recorded sync logger cleanup slice after command quoting issue.

### Backend stability / quality
- `f915df1` feat(logs): task-runs now include error retryability/category metadata for faster triage.
- `85201c3` feat(observability): added queue error-type catalog endpoint + Log Inspector reference table.
- `3bb8f5e` fix(worker): tolerate missing `task_runs` when reading checkpoints.
- `807639e` refactor(worker): centralize main-loop cancel handling.
- `8e049a5` fix(sync): skip malformed note IDs during note merge.
- `75ebfe9` fix(sync): skip stale note deletion when malformed IDs are present.
- `04cbc3f` fix(sync): make document note merge idempotent for duplicate incoming IDs.
- `28d331c` refactor(worker): centralize safe rollback handling in main loop.
- `920ef62` refactor(task-runs): centralize operation recovery/error wrapper.
- `edc1895` refactor(sync): extract shared note field mapping helper.
- `ed1ff4e` refactor(sync): use module logger consistently.

### Documents UX / triage
- `942c06b` context-aware empty-state messaging (`filtered` / `running_only` / `empty`).
- `4bc660e` running-only triage mode persisted in URL and active filter chips.
- `da0847b` copy-id action now shows transient "Copied" feedback.
- `d0da46f` add copy-id quick action in document rows.
- `64d2cc2` keyboard row activation in table (`Enter`/`Space`).
- `3cb3981` triage preset hotkeys (`Alt+1..4`).
- `d7283a7` running-only triage toggle.
- `80f3573` full clear-all action in quick controls.
- `e52ad5e` inline clear button in quick search.
- `919b862` sticky table header.
- `5f64229` direct page jump in table pagination.
- `37a82a0` visible-results summary in documents header.
- `775d2e9` actionable empty-state panel.
- `ccb15df` quick-search keyboard shortcuts (`/`, `Esc`).
- `d91e440` URL-synced quick search (`q`).
- `f178b02` triage preset bar.
- `f790311` reload button loading feedback.
- `0531246` split filters into primary + advanced sections.
- `e516f7f` active filter chips strip.

## 2026-02-14 (phase 2 start branch: feat/phase2-evidence-resolver)

### Phase 2 kickoff
- `a4f5542` feat(phase2): added `/chat/resolve-evidence` API contract and baseline resolver service (`app/services/evidence.py`) with bounded page processing and deterministic status outputs (`ok`/`no_match`/`error`), plus route-level tests.
- `4b47e82` feat(phase2): chat responses now enrich citations with baseline evidence metadata (`evidence_status`, `evidence_confidence`, `evidence_error`) using resolver pass for sufficiently long snippets; added service-level tests.
- `831c492` feat(phase2): chat citation UI now visualizes evidence state with status-colored source badges and tooltip details (status/confidence/error) for quicker trust checks.
- `82f2f70` feat(phase2): resolver now caps by unique `(doc_id,page)` coverage (not raw item count) and validates bbox geometry, returning explicit `invalid_bbox` errors where needed.
- `86d74f4` feat(phase2): moved evidence limits to runtime settings/env (`EVIDENCE_MAX_PAGES`, `EVIDENCE_MIN_SNIPPET_CHARS`), wired chat enrichment to settings values, added test coverage, and documented env vars in `.env.example` + `.env.worker.example`.
- `0968241` feat(phase2): added optional resolver fast path (`EVIDENCE_VECTOR_LOOKUP_ENABLED`) that tries to recover bbox from existing Qdrant chunk hits for the same `doc_id/page`, keeps strict fallback semantics (`no_match`/`error`), and adds dedicated service tests.
- `10f105a` perf(phase2): added per-request resolver cache for duplicate `(doc_id,page,source,snippet)` lookups to prevent repeated embed/search calls and reduce evidence latency.
- `3301c0a` feat(phase2): surfaced evidence resolver runtime config in `/status` payload (`evidence_vector_lookup_enabled`, `evidence_max_pages`, `evidence_min_snippet_chars`) with route test coverage.
- `56692c3` feat(phase2): surfaced evidence resolver runtime knobs in Operations > Runtime Configuration (frontend) for quick verification of active evidence behavior.
- `d6b80a8` feat(phase2): enforced `min_match_ratio` in evidence resolver (vector hits below threshold stay `no_match`), wired configurable default via `EVIDENCE_MIN_MATCH_RATIO`, surfaced the setting in status/Operations, and extended tests.
- `c9f5b18` refactor(phase2): removed unused bbox recovery logic (vector-lookup/min-ratio path) and related env/runtime UI knobs; evidence resolver now deterministically trusts only provided bbox and otherwise returns page-level `no_match`.
- `1fc3f81` feat(phase2): added real bbox resolution from PDF text-layer words (PyMuPDF) with snippet-to-word matching, per-request caching, chat + `/chat/resolve-evidence` integration, and committed non-sensitive PDF fixtures for repeatable tests.
- `dfe6145` feat(phase2): added persisted `document_page_anchors` index (migration + worker task `evidence_index`), wired pipeline missing-detection/continue fanout to include evidence indexing, and made evidence resolver prefer stored anchors (with PDF fallback) for retrieval-to-citation bbox mapping.
- `c76dc2f` feat(phase2): evidence index is now non-mandatory when indexing confirms `no_text_layer` for the source PDF; pipeline status marks evidence step optional/done in that case and avoids re-enqueueing `evidence_index` on sync followups.
- `2abdd84` feat(ux): chat now supports explicit follow-up context controls (toggle + turn depth + quick follow-up from prior message), and citation/detail links in both chat and search now open Document Details in a new tab while preserving `page` + `bbox` query payload for viewer focus.
- `cafe56f` feat(ux): added shared citation jump handoff service (`sessionStorage` token + query `jump`) so chat/search source links open in a new tab with resilient page/bbox pickup in Document Details, while keeping URL fallback params for direct links.
- `ecd4dd1` refactor(ux): Document Details now consumes-and-cleans one-time `jump` query tokens after citation handoff and reuses a shared query-copy helper to reduce duplicated route-query logic.
- `54f20aa` fix(chat): normalized chat citation numbering after source filtering/deduplication so citations remain contiguous (`[1..n]`) and follow-up references stay stable.
- `80952a5` feat(chat): introduced first-class `conversation_id` threading across chat request/response + stream done payload, persisted in chat store for follow-up continuity, and added backend tests for generated/echoed conversation IDs.
- `86aedbc` feat(chat): added explicit thread controls in Chat UI (`New thread`), surfaced active conversation id, and tagged each message with its conversation id for easier follow-up traceability.
- `cffbb6f` fix(chat): hardened prompt assembly by normalizing history (max turns + max chars per entry) before rendering, with regression tests to prevent oversized follow-up context payloads.
- `759c062` fix(ux): hardened citation jump handoff parsing to accept bbox strings/arrays consistently and added stale jump-token pruning in `sessionStorage` to avoid long-lived navigation residue.
- `74b541b` fix(chat-ui): markdown citation superscripts now render as plain markers when no document link is available, and citation tooltip/href attributes are escaped before HTML injection.
- `74f8b9b` refactor(chat-ui): extended generated `ChatCitation` typing with evidence fields and removed unsafe type-cast access in `ChatView` evidence rendering helpers.
- `da7eeb2` test(chat): added route-level tests for `/chat` and `/chat/stream` to verify `conversation_id` contract behavior in sync and SSE done-payload responses.
- `bc7b00b` feat(chat-ui): added active conversation-id copy action and normalized per-message thread separator to ASCII (`|`) for consistent rendering.
- `5c481ec` refactor(chat-store): extracted shared chat history/message builders to reduce duplication across streaming/non-streaming ask flows while preserving behavior.
- `511eaee` chore(chat): enriched chat route logging with source and `conversation_id` context for easier follow-up thread diagnostics in backend logs.
- `4e4dfb9` refactor(search): replaced Pinia-based search flow with `useSearchSession` (Vue Query mutation + generated client service), keeping SearchView state lean and composable-driven.
- `7896801` chore(search): removed unused `searchStore` after SearchView migration to composable-based Vue Query state.
- `4d3b92b` refactor(chat): replaced Pinia-driven chat view state with `useChatSession` (Vue Query mutation + generated client chat services) while preserving streaming, follow-up context, and local persistence behavior.
- `1a1c3ed` chore(chat): removed unused `chatStore` after composable migration to keep chat state architecture consistently Vue Query/composable-based.
- `41d2100` refactor(search): aligned search service signature with generated OpenAPI type `SearchEmbeddingsSearchGetParams` to keep request contracts strictly client-generated.
- `c39df21` refactor(chat): switched stream endpoint URL resolution to generated helper (`getChatStreamChatStreamPostUrl`) and tightened SSE done-payload typing for consistent OpenAPI-aligned chat contracts.
- `94c430b` refactor(search): moved embeddings search execution fully into `useSearchSession` via generated client (`searchEmbeddingsSearchGet`) + generated models, removing service-type coupling in the view/composable path.
- `1fb2ac0` refactor(chat): migrated chat execution path into `useChatSession` with direct generated client calls (`chatChatPost`) and generated stream URL helper usage for SSE, removing service-layer dependency from chat runtime flow.
- `a2f4861` chore(search): removed now-redundant `services/search.ts` wrapper after direct generated-client adoption in search composable/view flow.
- `ae7cf8c` chore(chat): removed redundant `services/chat.ts` wrapper and switched chat view typing to generated `ChatCitation` model, completing direct generated-client usage for chat/search paths.
- `4e6a696` feat(search): SearchView now keeps controls in URL query params (`q/k/src/v/minq/dd/rr`), auto-restores/reruns on reload, and adds explicit reset + deep-link copy actions for streamlined triage workflows.
- `61d9e60` feat(chat): Chat controls are now URL-synced (`k/src/v/minq/stream/hist/turns`) with quick reset + deep-link copy actions so chat sessions are easier to resume/share.
- `453a68f` fix(search): search controls now resync when route query changes via browser navigation, preventing stale UI state after back/forward transitions.
- `1000550` fix(chat): chat controls now resync from route-query changes during browser navigation so shared/back-forward links keep UI controls consistent.
- `0b18987` feat(search): improved empty-state clarity by distinguishing initial idle state from a completed query with no matches.
- `d42ecab` refactor(ui): introduced shared query-state helpers (`queryString/queryBool/queryNumber/isSameQueryState`) to reduce duplicated URL-sync logic across views.
- `4d728c0` refactor(search): switched SearchView URL-sync parsing/comparison to shared query-state helpers, reducing local duplication and keeping sync behavior consistent.
- `4347bc0` refactor(chat): switched ChatView URL-sync parsing/comparison to shared query-state helpers for consistent behavior and cleaner control-sync code.
- `c12f656` feat(search): added keyboard shortcuts (`/` focus query, `Ctrl+Enter` run search) for faster keyboard-driven triage/search workflows.
- `9f1d8d4` feat(chat): added keyboard shortcuts (`/` focus question, `Ctrl+Enter` ask) for parity with search and faster follow-up interactions.
- `d44b747` refactor(search): extracted global keyboard listener lifecycle into reusable `useGlobalHotkeys` composable and simplified SearchView hotkey wiring.
- `046c132` refactor(chat): switched ChatView hotkey listener lifecycle to shared `useGlobalHotkeys` composable for consistency with search.
- `84d8b00` refactor(ui): introduced reusable clipboard composable (`useClipboardCopy`) to centralize copy behavior/error mapping across views.
- `020d65e` feat(search): added per-result “Copy details link” quick action and switched search link copy flow to shared clipboard composable.
- `298cc2a` refactor(chat): switched chat copy actions (`Copy link`/`Copy id`) to shared clipboard composable for consistent UX/error handling.
- `a99630e` refactor(search): replaced SearchView’s local query-watch/sync flag boilerplate with shared `useRouteQuerySync` orchestration.
- `a837006` refactor(chat): replaced ChatView’s local query-watch/sync flag boilerplate with shared `useRouteQuerySync` orchestration.
- `d0f52f7` refactor(ui): added `useShareLink` composable to standardize link copy + toast feedback flows across views.
- `55302f5` refactor(ui): switched Search/Chat link-copy actions to shared `useShareLink` paths, reducing view-level copy/toast duplication.
- `34442f5` refactor(search): replaced SearchView’s inline keydown logic with shared `useInputCommandHotkeys` for slash-focus/Ctrl+Enter behavior.
- `1445ee8` refactor(chat): replaced ChatView’s inline keydown logic with shared `useInputCommandHotkeys` for slash-focus/Ctrl+Enter behavior.
- `aa3c2ad` refactor(ui): simplified hotkey composition by inlining listener lifecycle in `useInputCommandHotkeys` and removing obsolete `useGlobalHotkeys`.
- `5cfa94d` refactor(chat-search): removed duplicated local `syncToRoute` helpers in Chat/Search and reused `useRouteQuerySync` API directly for reset-triggered query updates.
- `f6b954f` refactor(ui): enhanced `useRouteQuerySync` with optional debounce and unknown-query-key preservation to reduce route-churn and avoid dropping unrelated URL state.
- `5f5f13e` perf(search): enabled debounced query-sync writes and preserved unrelated URL params in SearchView to keep navigation state stable while sliders/toggles change.
- `d38292f` perf(chat): enabled debounced query-sync writes and preserved unrelated URL params in ChatView to keep navigation state stable while control toggles change.
- `5cb53b6` feat(chat): chat draft question is now included in URL-synced state (`q`) so in-progress prompts can be resumed/shared alongside chat controls.
- `9255da2` feat(search): added `Ctrl+Shift+Enter` shortcut to open the first visible search result directly, accelerating keyboard-only review flow.
- `5b436e1` fix(ui): `useRouteQuerySync` now clears pending debounce timers on unmount to prevent delayed stale route updates after view teardown.
- `e75e990` feat(search): added inline shortcut hint text near search controls to improve discoverability of keyboard flow (`/`, `Ctrl+Enter`, `Ctrl+Shift+Enter`).
- `a137938` feat(search): reset action now clears stale results/error state in addition to control values, avoiding misleading old result lists after reset.
- `ba7307b` refactor(chat): moved chat control reset behavior into `useChatSession` to reduce view-level state mutation noise and ensure consistent error reset.
- `955e572` feat(chat): added inline shortcut hint text near chat controls to improve discoverability of keyboard ask flow (`/`, `Ctrl+Enter`).
- `3b96035` feat(chat): added per-message “Copy answer” quick action to speed reuse of generated responses without manual text selection.
- `729ea0d` feat(search): added per-result “Copy snippet” quick action to speed extraction of relevant text during review/triage.
- `2282b03` feat(chat): added `Ctrl+Shift+Enter` shortcut to open first citation from the latest answer for faster source navigation.
- `41af567` refactor(ui): introduced `useInputCommandHotkeys` to centralize shared slash-focus and Ctrl+Enter submit keyboard behavior for input-driven views.
- `9c23250` refactor(ui): added generic `useRouteQuerySync` composable to centralize query read/write/watch synchronization across route-driven views.

## Historical note
- Detailed older session bullets previously in `agents.md` are now expected in this changelog format going forward.
- For full historical record prior to this restructure, use git history (`git log --oneline` / `git log --stat`).
