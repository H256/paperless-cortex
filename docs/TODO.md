# TODO

## QA Findings (2026-02-14)

### Chat
- [x] Fix stream endpoint 404 (`POST /api/api/chat/stream`), ensure no double `/api` prefix.

### Logs
- [x] Increase bottom padding of error type reference section.
- [x] Replace free-text error-type filter with dropdown of discrete values.
- [x] Evaluate removing full-text search from logs view.

### Document Details
- [x] Summary note metadata date formatting: use compact format (`YYYY-MM-DD HH:mm:ss`).
- [x] Suggestions tab: prevent long "current" values from hiding action buttons; keep actions always reachable.
- [x] Confirm/clarify that `Vision OCR` source in Pages shows raw/un-cleaned text (or switch to cleaned text if intended).

### Writeback
- [x] Remove "Run Dry-Run Now" green button from Writeback page (use queue flow only).
- [x] Performance backlog: optimize dry-run preview for large Paperless datasets.
- [x] Add "remove from queue" capability for writeback queue items.

### Documents Page
- [x] Pagination input: clamp page input to valid max page.
- [x] Rework Triage vs Presets UX overlap (simplify mental model).
- [x] Add filter option: documents without correspondent.
- [x] Hide `PREV` button on first page and `NEXT` on last page.
- [x] Card view: show AI note; if missing, show best-pick (otherwise view has low value).

### Dashboard
- [x] Page count buckets: split `51+` into `51-99` and `100+`.
- [x] Top lists should show at least 10 entries.
- [x] Add relative ratios/percentages in evaluations.
- [x] Add pie chart tooltips (absolute + percentage).
- [x] Fix extended cards overflow on narrow screens (monthly processing, unprocessed by correspondent, document types).

## Ongoing backlog (post-QA)

- [ ] Continue responsive/mobile polish on detail-heavy screens (`DocumentDetail`, `Writeback`) and check overlap/overflow edge-cases on narrow widths.
- [ ] Add lightweight structured request timing logging for slow backend endpoints (route + duration + key params, without sensitive payloads).
- [ ] Add an optional compact worker-run timeline card in UI (recent task runs with error type + elapsed) for faster issue triage.
