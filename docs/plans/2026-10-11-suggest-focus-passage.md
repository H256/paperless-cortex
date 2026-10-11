# Plan: Guidance for "Suggest new" (marked passage and hint)

Date: 2026-10-11 · Issue: #381 · Tracking: #359 · Branch: `agent/381-suggest-focus-passage`

## Problem
"Suggest new" asks the model again with the same input, so a wrong value often comes back unchanged. The reviewer sees in the text where the answer is, but the model does not know. Because the suggestion LLM only sees OCR text, the useful guidance is a marked **passage** of that text and, optionally, a short **semantic hint** ("invoice date, not delivery date"), not layout hints.

## Design
- `POST /documents/{id}/suggestions/field` takes optional `focus_text` (max 2000 chars) and `hint` (max 300 chars). Control characters are removed, blank values are ignored, nothing changes without them.
- `build_reviewer_guidance()` (in `backend/app/services/ai/suggestions.py`) builds a prefix for the field prompt. The hint is a plain instruction; the focus passage is document content and is wrapped by `fence_untrusted_text()`, so it cannot break out of the data fence.
- The queued path (`suggest_field` worker task) carries both values; the direct path (priority) passes them to the generator. Both only add keyword arguments when present, so existing call signatures and fakes stay valid.
- UI: a "Guidance for Suggest new" section above the panels (collapsed unless guidance is active): document text with a source switch (Paperless / Vision OCR), "Use selected text as focus" (reads the browser selection and only accepts selections inside the text box), a hint input and a focus chip with "Clear". The guidance is sent with every Suggest new / Generate variants request of the page; nothing is applied automatically.

## Tests
- `test_suggestion_llm_helper.py`: guidance is empty without input, focus is fenced and limited, prompt starts with the guidance only when given.
- `test_documents_suggestions_routes.py`: focus/hint reach the generator; unchanged call without guidance.
- `test_worker_suggest_field.py`: queued focus/hint are forwarded.
- `DocumentSuggestionsSection.test.ts`: marking a passage, hint, emitted guidance, no guidance by default, rejected outside selection, clearing.

## Not included
Page restriction, choosing the OCR source for the model text, and "do not repeat rejected variants" stay in #359.
