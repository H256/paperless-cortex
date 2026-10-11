# Plan: Review mode (previous/next in the filtered list)

Date: 2026-10-11 · Issue: #369 · Tracking: #359 · Branch: `agent/369-review-mode-prev-next` (from `develop`)

## Goal
Work through "Unreviewed" / "Needs review" documents without going back to the list after every document.

## Design
- The documents list stores the ordered ids of the currently visible (filtered, sorted) page in `localStorage` (`review_queue_v1`). A watcher keeps it current, so links opened in a new tab work as well.
- The document detail view finds its document in that list and offers Previous / Next with the position ("3 / 20"), keyboard `k` / `j` (ignored while typing) and an **Auto-advance** toggle.
- `return_to` and the active tab are kept when navigating, so the reviewer stays on e.g. the Suggestions tab.
- Auto-advance runs after "Mark reviewed" or "Write back" **only if the document is `reviewed` afterwards**. "Apply selected" never navigates.
- Documents that are not part of the stored list (direct link, similar documents) show no controls; behavior is unchanged.

## Files
- `frontend/src/utils/reviewQueue.ts` (storage, position, settings)
- `frontend/src/composables/useReviewQueue.ts` (navigation, keyboard, auto-advance)
- `frontend/src/components/DocumentDetailHeader.vue` (controls)
- `frontend/src/views/DocumentDetailView.vue`, `frontend/src/views/DocumentsView.vue` (wiring)

## Tests
- Storage/position utils, composable (navigation, keyboard, auto-advance), header component.
- Full frontend suite, `vue-tsc --build`, `oxlint`.

## Out of scope (stays in #359)
- Continuing across list pages, prefetching the next document, server-side neighbors for very large result sets.
- Deterministic date/correspondent candidates, passage focus for "Suggest new".
