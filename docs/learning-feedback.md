# Feedback-Driven Suggestions (Self-Reinforcing Loop)

## Goal
Turn explicit user actions (accept/override) into feedback that improves future suggestions, without auto-writing to Paperless.

---

## 1) Capture feedback events
Log every suggestion application or manual correction as a structured event:
- `doc_id`, `field`, `original_suggestion`, `final_value`
- `source` (`paperless_ocr` / `vision_ocr` / `manual`)
- document snapshot features (correspondent, tags, doc type, date, keywords)
- model info (prompt version, model, timestamp)

This becomes the training dataset and memory.

---

## 2) Feedback memory (retrieval)
Before new LLM calls, retrieve *similar past corrections*:
- Embed “doc context + field”
- Store each correction as a retrievable case
- Query top-k similar cases
- Inject them into the prompt as preferences

Example for **title**:
- “In similar invoices, we prefer: `Vendor – Invoice #123 – YYYY-MM-DD`”
- “We always drop ‘GmbH’ from titles”

This adapts quickly without fine-tuning.

---

## 3) Per-field rules (deterministic)
Mine frequent corrections into rules with confidence thresholds:
- For a **correspondent**: preferred title/date format, default tags
- For a **doc type**: typical tags, title templates
- For **keywords**: forced tags/correspondents

Apply only to *suggestions*, never writeback automatically.

---

## 4) Lightweight model adaptation
### Option A: Reranker/classifier
Train a small model per field (or a single multi-field model):
- Input: document features + candidate suggestion
- Output: acceptance probability

Use it to reorder or filter suggestions.

### Option B: LLM few-shot + retrieval
Feed top-k “similar corrections” as examples.

Avoid full fine-tuning; keep inference cheap and safe.

---

## 5) Feedback-aware prompting
Add a “user preferences” block to the prompt:
- Past corrections
- Formatting rules
- Example titles/tags that were accepted

This biases outputs toward your accepted patterns.

---

## 6) Safety model
- Never auto-write to Paperless
- Always show “source: learned preference”
- Per-field “Ignore learned rules” toggle

---

## 7) Metrics & evaluation
Track:
- acceptance rate before/after
- manual edits after accept
- time saved per doc

If those improve, the loop is working.

---

## Note on Reranking
Reranking can be driven by retrieval from *paperless_ocr* and *vision_ocr* vectors:
- Retrieve top-k similar past corrections based on embeddings
- Use those as features for scoring candidates
- Combine with rule-based boosts for correspondents/tags

This keeps the system grounded in your actual edits.
