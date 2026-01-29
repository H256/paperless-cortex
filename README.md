# Paperless Intelligence (Arcane)

## Concise flow
1) **Sync metadata + OCR**  
   The backend pulls document metadata and the Paperless OCR text via API and stores them in Postgres.

2) **Page text layers**  
   - If the Paperless OCR text contains form-feed page breaks, it is split into pages.  
   - Otherwise, the PDF is downloaded and text is extracted per page (pdfminer).  
   - If vision OCR is enabled, pages are rendered to images and sent to Ollama for OCR.  
     On re-processing (`force_embed=true`) all pages go through vision OCR.

3) **Quality scoring**  
   Each page is scored with heuristic metrics (length, alnum ratio, vowel ratio, word-likeness, etc.).  
   Scores are logged and attached to the chunk payload as `quality_score`.

4) **Embeddings (dual-layer)**  
   For every page, chunks are created and embedded for both layers:  
   - baseline text (Paperless OCR / pdfminer extraction)  
   - vision OCR text  
   Each Qdrant point stores `doc_id`, `page`, `source`, and `quality_score`.

5) **Search**  
   `/embeddings/search` returns matches with `doc_id`, `page`, `snippet`, `score`, `source`, and `quality_score`.

## Notes
- Paperless remains the source of truth; no automatic writeback is performed.  
- Vision OCR is optional and controlled by env (`ENABLE_VISION_OCR`, `VISION_MODEL`).  
- Re-process uses full vision OCR to improve handwritten/low-quality pages.
