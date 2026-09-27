"""Centralized document-cache invalidation.

Every document mutation must invalidate the full set of local document caches
through this helper so that no single mutation path can forget one of the five
caches (dashboard, stats, list, local-document, page-texts).
"""

from __future__ import annotations

from app.services.documents.dashboard_cache import invalidate_dashboard_cache
from app.services.documents.document_stats_cache import invalidate_document_stats_cache
from app.services.documents.documents_list_cache import invalidate_documents_list_cache
from app.services.documents.local_document_cache import invalidate_local_document_cache
from app.services.documents.page_texts_cache import invalidate_page_texts_cache


def invalidate_document_caches(doc_id: int | None = None) -> None:
    """Invalidate all local document caches.

    When ``doc_id`` is ``None`` every cache is cleared globally; otherwise the
    document-scoped caches (local document, page texts) are invalidated only for
    that document while the aggregate caches (dashboard, stats, list) are always
    cleared globally because they roll up per-document data.
    """
    invalidate_dashboard_cache()
    invalidate_document_stats_cache()
    invalidate_documents_list_cache()
    invalidate_local_document_cache(doc_id)
    invalidate_page_texts_cache(doc_id)
