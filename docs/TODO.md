# TODO

## QA Findings (2026-02-14)

### Chat
- [ ] Fix stream endpoint 404 (`POST /api/api/chat/stream`), ensure no double `/api` prefix.

### Logs
- [ ] Increase bottom padding of error type reference section.
- [ ] Replace free-text error-type filter with dropdown of discrete values.
- [ ] Evaluate removing full-text search from logs view.

### Document Details
- [ ] Summary note metadata date formatting: use compact format (`YYYY-MM-DD HH:mm:ss`).
- [ ] Suggestions tab: prevent long "current" values from hiding action buttons; keep actions always reachable.
- [ ] Confirm/clarify that `Vision OCR` source in Pages shows raw/un-cleaned text (or switch to cleaned text if intended).

### Writeback
- [ ] Remove "Run Dry-Run Now" green button from Writeback page (use queue flow only).
- [ ] Performance backlog: optimize dry-run preview for large Paperless datasets.
- [ ] Add "remove from queue" capability for writeback queue items.

### Documents Page
- [ ] Pagination input: clamp page input to valid max page.
- [ ] Rework Triage vs Presets UX overlap (simplify mental model).
- [ ] Add filter option: documents without correspondent.
- [ ] Hide `PREV` button on first page and `NEXT` on last page.
- [ ] Card view: show AI note; if missing, show best-pick (otherwise view has low value).

### Dashboard
- [ ] Page count buckets: split `51+` into `51-99` and `100+`.
- [ ] Top lists should show at least 10 entries.
- [ ] Add relative ratios/percentages in evaluations.
- [ ] Add pie chart tooltips (absolute + percentage).
- [ ] Fix extended cards overflow on narrow screens (monthly processing, unprocessed by correspondent, document types).
