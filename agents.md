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
1. Phase 2 planning and delivery slices (evidence locator + bbox enrichment path).
2. Load/real-world validation on large documents and production-like queue behavior.
3. Continue strict KISS/DRY/SOLID cleanup during feature work.

## Open work (high-level)
- Implement Phase 2 evidence-resolution endpoint and chat pipeline integration.
- Add targeted integration tests for bbox evidence fallback behavior.
- Continue UX polish where operational friction is still observed.

## Working agreements
- No commits on `master`.
- Frequent small commits with clear scope.
- Update this file only with big-picture state.
- Put granular per-slice history into `CHANGELOG.md`.
- Every change set should be documented in `CHANGELOG.md` and include the git hash whenever available.
