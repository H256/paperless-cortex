# Verification Checklist (2026-02-02)

- Backend: run Alembic migration `c4f9b8e1d2a3_add_ai_model_fields` and verify new columns populate on new suggestion/vision runs.
- Queue: start two worker processes; confirm second exits due to lock.
- Queue UI: filter by Doc ID, reorder filtered item, verify actual queue order changes.
- Documents UI: apply a suggestion, confirm suggestions/page texts/quality reload.
- Documents UI: continue-processing modal options change preview counts and enqueue only selected tasks.
- Documents UI: model filter matches `analysis_model` values.
- Queue stats: after processing at least one item, verify "Last run" and ETA are based on last run duration.
