# agents.md (Compact)

## Goal
Build a robust, safe Paperless intelligence layer:
- local-first AI processing
- explicit manual writeback
- strong retrieval/search/chat foundation
- stable, observable worker pipeline

## Phase status
- `MVP`: **Done**
- `Phase 1 (robustness + UX)`: **Done**
- `Phase 2 (advanced evidence locator with bbox on-demand)`: **In progress**

## What is stable now
- Sync + local cache + manual writeback flow
- Queue/worker processing with retries and task-run tracking
- Dual-source suggestions (paperless/vision) with best-pick workflow
- Large-document path (page notes + hierarchical summary)
- Continue-processing and triage UX with URL-synced filters

## Current branch
- Active branch: `perf/ops-route-speedups`

## Current focus (short-term)
1. UX/mobile polish pass for document operations and continue-processing ergonomics.
2. Backend SRP refactor of largest route modules by extracting pipeline/writeback planning helpers into services.
3. Continue strict KISS/DRY/SOLID cleanup during feature work.

## Session handover (2026-02-14)
- Fixed false `Sync: Missing` after writeback by invalidating Paperless caches and reading fresh modified timestamp for reviewed/audit updates.
- Fixed writeback preview gap where only a subset of changed docs appeared; `only_changed` now uses local candidate discovery (audit + pending tags).
- Added summary-only suggestion regeneration (`field=note` variants mapped to `summary`) and updated Suggestions UI.
- Suggestions UX cleanup: inline variants under each field, removed legacy tag debug hint boxes.

## Open work (high-level)
- Complete responsive/mobile fit-and-finish across key screens (documents, processing, detail-heavy actions).
- Continue extracting large route logic into dedicated services/composables to reduce coupling.
- Validate changes under large-dataset load and queue-heavy scenarios before release.

## Working agreements
- No commits on `master`.
- Frequent small commits with clear scope.
- Update this file only with big-picture state.
- Put granular per-slice history into `CHANGELOG.md`.
- Every change set should be documented in `CHANGELOG.md` and include the git hash whenever available.
