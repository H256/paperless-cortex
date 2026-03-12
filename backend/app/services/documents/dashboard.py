from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import and_, case, exists, func, or_

from app.models import (
    Correspondent,
    Document,
    DocumentEmbedding,
    DocumentPageText,
    DocumentSuggestion,
    DocumentType,
    Tag,
    document_tags,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def build_dashboard_payload(db: Session) -> dict[str, object]:
    is_processed = and_(
        exists().where(DocumentEmbedding.doc_id == Document.id),
        exists().where(and_(DocumentPageText.doc_id == Document.id, DocumentPageText.source == "vision_ocr")),
        exists().where(DocumentSuggestion.doc_id == Document.id),
    )
    embedding_exists = exists().where(DocumentEmbedding.doc_id == Document.id)
    vision_exists = exists().where(
        and_(DocumentPageText.doc_id == Document.id, DocumentPageText.source == "vision_ocr")
    )
    suggestion_exists = exists().where(DocumentSuggestion.doc_id == Document.id)

    aggregate_row = db.query(
        func.count(Document.id).label("total"),
        func.sum(case((embedding_exists, 1), else_=0)).label("embeddings"),
        func.sum(case((vision_exists, 1), else_=0)).label("vision"),
        func.sum(case((suggestion_exists, 1), else_=0)).label("suggestions"),
        func.sum(case((is_processed, 1), else_=0)).label("fully_processed"),
        func.sum(
            case((and_(Document.correspondent_id.is_(None), ~is_processed), 1), else_=0)
        ).label("unassigned_unprocessed"),
        func.sum(case((or_(Document.page_count.is_(None), Document.page_count < 1), 1), else_=0)).label("unknown"),
        func.sum(case((Document.page_count == 1, 1), else_=0)).label("p1"),
        func.sum(case((and_(Document.page_count >= 2, Document.page_count <= 3), 1), else_=0)).label("p2_3"),
        func.sum(case((and_(Document.page_count >= 4, Document.page_count <= 6), 1), else_=0)).label("p4_6"),
        func.sum(case((and_(Document.page_count >= 7, Document.page_count <= 10), 1), else_=0)).label("p7_10"),
        func.sum(case((and_(Document.page_count >= 11, Document.page_count <= 20), 1), else_=0)).label("p11_20"),
        func.sum(case((and_(Document.page_count >= 21, Document.page_count <= 50), 1), else_=0)).label("p21_50"),
        func.sum(case((and_(Document.page_count >= 51, Document.page_count <= 99), 1), else_=0)).label("p51_99"),
        func.sum(case((Document.page_count >= 100, 1), else_=0)).label("p100p"),
    ).one()
    total_docs = int(aggregate_row.total or 0)
    fully_processed = int(aggregate_row.fully_processed or 0)
    stats = {
        "total": total_docs,
        "processed": int(aggregate_row.embeddings or 0),
        "unprocessed": max(0, total_docs - fully_processed),
        "embeddings": int(aggregate_row.embeddings or 0),
        "vision": int(aggregate_row.vision or 0),
        "suggestions": int(aggregate_row.suggestions or 0),
        "fully_processed": fully_processed,
    }

    correspondents_rows = (
        db.query(
            Correspondent.id,
            Correspondent.name,
            func.count(Document.id).label("total_count"),
            func.sum(case((~is_processed, 1), else_=0)).label("unprocessed_count"),
        )
        .join(Document, Document.correspondent_id == Correspondent.id)
        .group_by(Correspondent.id)
        .order_by(func.count(Document.id).desc(), Correspondent.name.asc())
        .all()
    )
    assigned_count = sum(int(row[2] or 0) for row in correspondents_rows)
    unassigned_count = max(0, total_docs - assigned_count)
    correspondents = [{"id": row[0], "name": row[1] or "Untitled", "count": row[2]} for row in correspondents_rows]
    if unassigned_count:
        correspondents.append({"id": None, "name": "Unassigned correspondent", "count": unassigned_count})
    correspondents.sort(key=lambda item: item["count"], reverse=True)
    top_correspondents = correspondents[:10]

    tag_rows = (
        db.query(Tag.id, Tag.name, func.count(document_tags.c.document_id))
        .join(document_tags, Tag.id == document_tags.c.tag_id)
        .group_by(Tag.id)
        .order_by(func.count(document_tags.c.document_id).desc(), Tag.name.asc())
        .all()
    )
    tagged_docs_count = int(db.query(func.count(func.distinct(document_tags.c.document_id))).scalar() or 0)
    untagged_count = max(0, total_docs - tagged_docs_count)
    tags = [{"id": row[0], "name": row[1] or "Untitled", "count": row[2]} for row in tag_rows]
    if untagged_count:
        tags.append({"id": None, "name": "No tags", "count": untagged_count})
    tags.sort(key=lambda item: item["count"], reverse=True)
    top_tags = tags[:10]

    type_rows = (
        db.query(DocumentType.id, DocumentType.name, func.count(Document.id))
        .join(Document, Document.document_type_id == DocumentType.id)
        .group_by(DocumentType.id)
        .order_by(func.count(Document.id).desc(), DocumentType.name.asc())
        .all()
    )
    typed_count = sum(int(row[2] or 0) for row in type_rows)
    type_unknown = max(0, total_docs - typed_count)
    document_types = [{"id": row[0], "name": row[1] or "Untitled", "count": row[2]} for row in type_rows]
    if type_unknown:
        document_types.append({"id": None, "name": "No document type", "count": type_unknown})
    document_types.sort(key=lambda item: item["count"], reverse=True)

    month_expr = func.coalesce(
        func.nullif(func.substr(Document.document_date, 1, 7), ""),
        func.nullif(func.substr(Document.created, 1, 7), ""),
        "Unknown",
    )
    monthly_rows = (
        db.query(
            month_expr.label("month"),
            func.count(Document.id).label("total"),
            func.sum(case((is_processed, 1), else_=0)).label("processed"),
            func.sum(case((is_processed, 0), else_=1)).label("unprocessed"),
        )
        .group_by("month")
        .order_by("month")
        .all()
    )

    correspondents_map = {
        int(row[0]): str(row[1] or "Untitled")
        for row in correspondents_rows
        if row[0] is not None
    }
    unprocessed_corr_list = [
        {
            "id": row[0],
            "name": correspondents_map.get(int(row[0]))
            or ("Unassigned correspondent" if row[0] is None else "Untitled"),
            "count": int(row[3] or 0),
        }
        for row in correspondents_rows
        if int(row[3] or 0) > 0
    ]
    if int(aggregate_row.unassigned_unprocessed or 0):
        unprocessed_corr_list.append(
            {
                "id": None,
                "name": "Unassigned correspondent",
                "count": int(aggregate_row.unassigned_unprocessed or 0),
            }
        )
    unprocessed_corr_list.sort(key=lambda item: item["count"], reverse=True)

    monthly_processing = [
        {
            "label": str(row.month),
            "total": int(row.total or 0),
            "processed": int(row.processed or 0),
            "unprocessed": int(row.unprocessed or 0),
        }
        for row in monthly_rows
    ]
    if monthly_processing and monthly_processing[0]["label"] == "Unknown":
        monthly_processing = [*monthly_processing[1:], monthly_processing[0]]

    page_counts = [
        {"label": "1", "count": int(aggregate_row.p1 or 0)},
        {"label": "2-3", "count": int(aggregate_row.p2_3 or 0)},
        {"label": "4-6", "count": int(aggregate_row.p4_6 or 0)},
        {"label": "7-10", "count": int(aggregate_row.p7_10 or 0)},
        {"label": "11-20", "count": int(aggregate_row.p11_20 or 0)},
        {"label": "21-50", "count": int(aggregate_row.p21_50 or 0)},
        {"label": "51-99", "count": int(aggregate_row.p51_99 or 0)},
        {"label": "100+", "count": int(aggregate_row.p100p or 0)},
        {"label": "Unknown", "count": int(aggregate_row.unknown or 0)},
    ]

    return {
        "stats": stats,
        "correspondents": correspondents,
        "top_correspondents": top_correspondents,
        "tags": tags,
        "top_tags": top_tags,
        "page_counts": page_counts,
        "document_types": document_types,
        "unprocessed_by_correspondent": unprocessed_corr_list,
        "monthly_processing": monthly_processing,
    }
