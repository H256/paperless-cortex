from __future__ import annotations

from typing import Any

from app.models import Document, DocumentType, SuggestionAudit, Tag
from app.services.ai.correspondent_rules import (
    build_learned_rules_instruction,
    learn_correspondent_rules,
)


def _seed(
    db: Any,
    *,
    doc_id: int,
    correspondent_id: int | None,
    reviewed_ids: list[int],
    tags: list[tuple[int, str]],
    types: list[tuple[int, str]],
) -> None:
    tag_objs: dict[int, Any] = {}
    type_objs: dict[int, Any] = {}
    for tag_id, name in tags:
        obj = Tag(id=tag_id, name=name)
        tag_objs[tag_id] = obj
        db.add(obj)
    for type_id, name in types:
        obj = DocumentType(id=type_id, name=name)
        type_objs[type_id] = obj
        db.add(obj)
    db.add(Document(id=doc_id, correspondent_id=correspondent_id))
    # Reviewed docs of the correspondent, each carrying one tag and one type.
    for idx, rid in enumerate(reviewed_ids):
        doc = Document(id=rid, correspondent_id=correspondent_id)
        if idx < len(tags):
            doc.tags = [tag_objs[tags[idx][0]]]
        if idx < len(types):
            doc.document_type_id = types[idx][0]
        db.add(doc)
        db.add(
            SuggestionAudit(
                doc_id=rid,
                action="apply_to_document:title",
                source="paperless_ocr",
                created_at="2026-02-20T10:00:00+00:00",
            )
        )
    db.commit()


def test_learn_rules_empty_when_no_correspondent(session_factory: Any) -> None:
    with session_factory() as db:
        db.add(Document(id=1, correspondent_id=None))
        db.commit()
        assert learn_correspondent_rules(db, 1) == {}


def test_learn_rules_empty_when_no_reviewed_docs(session_factory: Any) -> None:
    with session_factory() as db:
        tag_rechnung = Tag(id=1, name="rechnung")
        db.add(tag_rechnung)
        db.add(Document(id=1, correspondent_id=100))
        # A doc of the correspondent that was NOT reviewed.
        doc5 = Document(id=5, correspondent_id=100)
        doc5.tags = [tag_rechnung]
        db.add(doc5)
        db.commit()
        assert learn_correspondent_rules(db, 1) == {}


def test_learn_rules_aggregates_reviewed_patterns(session_factory: Any) -> None:
    with session_factory() as db:
        _seed(
            db,
            doc_id=1,
            correspondent_id=100,
            reviewed_ids=[5, 6, 7],
            tags=[(1, "rechnung"), (2, "hosting"), (3, "internet")],
            types=[(1, "Rechnung"), (2, "Vertrag"), (3, "Brief")],
        )
        rules = learn_correspondent_rules(db, 1)
        assert rules["correspondent_id"] == 100
        assert sorted(rules["top_tags"]) == ["hosting", "internet", "rechnung"]
        assert sorted(rules["top_document_types"]) == ["Brief", "Rechnung", "Vertrag"]


def test_learn_rules_ignores_unreviewed_doc_patterns(session_factory: Any) -> None:
    with session_factory() as db:
        tag_rechnung = Tag(id=1, name="rechnung")
        db.add(tag_rechnung)
        db.add(DocumentType(id=1, name="Rechnung"))
        db.add(Document(id=1, correspondent_id=100))
        # Reviewed doc 5 has the tag; unreviewed doc 9 has a different tag.
        doc5 = Document(id=5, correspondent_id=100)
        doc5.tags = [tag_rechnung]
        db.add(doc5)
        db.add(
            SuggestionAudit(
                doc_id=5,
                action="mark_reviewed",
                source="manual",
                created_at="2026-02-20T10:00:00+00:00",
            )
        )
        tag_other = Tag(id=2, name="unreviewed-tag")
        db.add(tag_other)
        doc9 = Document(id=9, correspondent_id=100)
        doc9.tags = [tag_other]
        db.add(doc9)
        db.commit()
        rules = learn_correspondent_rules(db, 1)
        assert rules["top_tags"] == ["rechnung"]


def test_build_instruction_empty_for_empty_rules() -> None:
    assert build_learned_rules_instruction({}) == ""
    assert build_learned_rules_instruction(None) == ""


def test_build_instruction_renders_patterns() -> None:
    text = build_learned_rules_instruction(
        {"correspondent_id": 100, "top_tags": ["rechnung"], "top_document_types": ["Rechnung"]}
    )
    assert "Typical tags: rechnung" in text
    assert "Typical document types: Rechnung" in text


def test_build_instruction_only_types() -> None:
    text = build_learned_rules_instruction({"top_tags": [], "top_document_types": ["Brief"]})
    assert "Typical tags" not in text
    assert "Typical document types: Brief" in text
