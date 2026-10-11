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


## Slice 2: paging across list pages and prefetch (#371)

- The documents list stores the list request (filters, ordering, page size), the loaded page range, the client-side filters and the ids that already have suggestions.
- **Continuing**: when at most 2 documents are left the next ones are loaded in the background and appended; `j` waits for the load if the end was reached.
- **Stable lists** continue with `lastPage + 1`, and `k` can load the previous page.
- **Shrinking lists** (`unreviewed`, `needs_review`): reviewed documents leave the server list, so `page + 1` would skip rows. These are re-scanned from page 1 and only documents not yet in the queue are appended; paging backwards is not offered.
- "Running only" depends on live task state and disables paging.
- **Prefetch**: ~0.6 s after a document is shown, the next document (`/local`) is requested ahead of time; suggestions only if the list row already had suggestions, so prefetching never triggers generation. A single-use in-memory cache (TTL 20 s, max 6 entries) is consumed by the loaders.
- Position shows `3 / 20+` while more documents can be loaded.

## Out of scope (stays in #359)
- Server-side neighbor endpoint for very large result sets.
- Deterministic date/correspondent candidates, passage focus for "Suggest new".
