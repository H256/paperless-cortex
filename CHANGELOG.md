# Changelog

All granular implementation slices and refactors are tracked here.
`agents.md` keeps only high-level project state.

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

## Historical note
- Detailed older session bullets previously in `agents.md` are now expected in this changelog format going forward.
- For full historical record prior to this restructure, use git history (`git log --oneline` / `git log --stat`).
