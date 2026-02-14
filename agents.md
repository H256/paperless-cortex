# agents.md (Compact)

## Goal
Build a robust, safe Paperless intelligence layer:
- local-first AI processing
- explicit manual writeback
- strong retrieval/search/chat foundation
- stable, observable worker pipeline

## Phase status
- `MVP`: **Done**
- `Phase 1 (robustness + UX)`: **In progress (late)**
- `Phase 2 (advanced evidence locator with bbox on-demand)`: **Planned**

## What is stable now
- Sync + local cache + manual writeback flow
- Queue/worker processing with retries and task-run tracking
- Dual-source suggestions (paperless/vision) with best-pick workflow
- Large-document path (page notes + hierarchical summary)
- Continue-processing and triage UX with URL-synced filters

## Current branch
- Active branch: `feat/documents-triage-presets-search`

## Current focus (short-term)
1. Backend stability hardening (sync/worker edge cases, retry safety, rollback safety).
2. UX friction removal for document triage and processing visibility.
3. Keep codebase lean: KISS/DRY/SOLID, composables/components, generated API client + vue-query.

## Open work (high-level)
- Finish Phase 1 hardening pass (error taxonomy clarity, worker observability polish).
- Validate full end-to-end behavior on large docs under real load.
- Prepare focused Phase 2 implementation slice for evidence locator.

## Working agreements
- No commits on `master`.
- Frequent small commits with clear scope.
- Update this file only with big-picture state.
- Put granular per-slice history into `CHANGELOG.md`.
- Every change set should be documented in `CHANGELOG.md` and include the git hash whenever available.
