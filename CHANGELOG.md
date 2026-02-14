# Changelog

All granular implementation slices and refactors are tracked here.
`agents.md` keeps only high-level project state.

## 2026-02-14 (current branch: feat/documents-triage-presets-search)

### Backend stability / quality
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

## Historical note
- Detailed older session bullets previously in `agents.md` are now expected in this changelog format going forward.
- For full historical record prior to this restructure, use git history (`git log --oneline` / `git log --stat`).
