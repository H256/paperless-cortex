from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table, Text, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


document_tags = Table(
    "document_tags",
    Base.metadata,
    Column("document_id", ForeignKey("documents.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str | None] = mapped_column(String(512))
    content: Mapped[str | None] = mapped_column(Text)
    correspondent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("correspondents.id")
    )
    document_type_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("document_types.id")
    )
    document_date: Mapped[str | None] = mapped_column(String(32))
    created: Mapped[str | None] = mapped_column(String(32))
    modified: Mapped[str | None] = mapped_column(String(64))
    added: Mapped[str | None] = mapped_column(String(64))
    archive_serial_number: Mapped[int | None] = mapped_column(Integer)
    original_file_name: Mapped[str | None] = mapped_column(String(512))
    mime_type: Mapped[str | None] = mapped_column(String(128))
    page_count: Mapped[int | None] = mapped_column(Integer)
    owner_id: Mapped[int | None] = mapped_column(Integer)
    user_can_change: Mapped[bool | None] = mapped_column(Boolean)
    is_shared_by_requester: Mapped[bool | None] = mapped_column(Boolean)
    deleted_at: Mapped[str | None] = mapped_column(String(128))
    analysis_model: Mapped[str | None] = mapped_column(String(128))
    analysis_processed_at: Mapped[str | None] = mapped_column(String(64))

    notes: Mapped[list["DocumentNote"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    tags: Mapped[list["Tag"]] = relationship(
        secondary=document_tags, back_populates="documents"
    )

    correspondent: Mapped["Correspondent | None"] = relationship(
        back_populates="documents"
    )
    document_type: Mapped["DocumentType | None"] = relationship(
        back_populates="documents"
    )


class DocumentNote(Base):
    __tablename__ = "document_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    created: Mapped[str | None] = mapped_column(String(64))
    user_id: Mapped[int | None] = mapped_column(Integer)
    user_username: Mapped[str | None] = mapped_column(String(128))
    user_first_name: Mapped[str | None] = mapped_column(String(128))
    user_last_name: Mapped[str | None] = mapped_column(String(128))

    document: Mapped[Document] = relationship(back_populates="notes")


class SyncState(Base):
    __tablename__ = "sync_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_synced_at: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str | None] = mapped_column(String(32))
    total: Mapped[int | None] = mapped_column(Integer)
    processed: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[str | None] = mapped_column(String(64))
    cancel_requested: Mapped[bool | None] = mapped_column(Boolean)


class DocumentEmbedding(Base):
    __tablename__ = "document_embeddings"

    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    content_hash: Mapped[str | None] = mapped_column(String(128))
    embedding_model: Mapped[str | None] = mapped_column(String(128))
    embedded_at: Mapped[str | None] = mapped_column(String(64))
    embedding_source: Mapped[str | None] = mapped_column(String(32))
    chunk_count: Mapped[int | None] = mapped_column(Integer)


class DocumentPageText(Base):
    __tablename__ = "document_page_texts"

    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    page: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    text: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    clean_text: Mapped[str | None] = mapped_column(Text)
    token_estimate_raw: Mapped[int | None] = mapped_column(Integer)
    token_estimate_clean: Mapped[int | None] = mapped_column(Integer)
    cleaned_at: Mapped[str | None] = mapped_column(String(64))
    quality_score: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str | None] = mapped_column(String(64))
    model_name: Mapped[str | None] = mapped_column(String(128))
    processed_at: Mapped[str | None] = mapped_column(String(64))

    document: Mapped[Document] = relationship()


class DocumentSuggestion(Base):
    __tablename__ = "document_suggestions"

    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(String(64))
    model_name: Mapped[str | None] = mapped_column(String(128))
    processed_at: Mapped[str | None] = mapped_column(String(64))

    document: Mapped[Document] = relationship()


class DocumentPageNote(Base):
    __tablename__ = "document_page_notes"

    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    page: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    notes_text: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str | None] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(String(64))
    processed_at: Mapped[str | None] = mapped_column(String(64))

    document: Mapped[Document] = relationship()


class DocumentSectionSummary(Base):
    __tablename__ = "document_section_summaries"

    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    section_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    summary_text: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str | None] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(String(64))
    processed_at: Mapped[str | None] = mapped_column(String(64))

    document: Mapped[Document] = relationship()


class DocumentPageAnchor(Base):
    __tablename__ = "document_page_anchors"

    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    page: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    anchors_json: Mapped[str | None] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(String(64))
    processed_at: Mapped[str | None] = mapped_column(String(64))

    document: Mapped[Document] = relationship()


class DocumentOcrScore(Base):
    __tablename__ = "document_ocr_scores"

    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    content_hash: Mapped[str | None] = mapped_column(String(128))
    quality_score: Mapped[float | None] = mapped_column(Float)
    verdict: Mapped[str | None] = mapped_column(String(32))
    components_json: Mapped[str | None] = mapped_column(Text)
    noise_json: Mapped[str | None] = mapped_column(Text)
    ppl_json: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[str | None] = mapped_column(String(64))
    processed_at: Mapped[str | None] = mapped_column(String(64))

    document: Mapped[Document] = relationship()


class SuggestionAudit(Base):
    __tablename__ = "suggestion_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    action: Mapped[str] = mapped_column(String(64))
    source: Mapped[str | None] = mapped_column(String(32))
    field: Mapped[str | None] = mapped_column(String(32))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(String(64))

    document: Mapped[Document] = relationship()


class WritebackJob(Base):
    __tablename__ = "writeback_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    docs_selected: Mapped[int] = mapped_column(Integer, default=0)
    docs_changed: Mapped[int] = mapped_column(Integer, default=0)
    calls_count: Mapped[int] = mapped_column(Integer, default=0)
    doc_ids_json: Mapped[str | None] = mapped_column(Text)
    calls_json: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[str | None] = mapped_column(String(64))
    finished_at: Mapped[str | None] = mapped_column(String(64))


class TaskRun(Base):
    __tablename__ = "task_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    doc_id: Mapped[int | None] = mapped_column(Integer, index=True)
    task: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str | None] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    worker_id: Mapped[str | None] = mapped_column(String(128))
    payload_json: Mapped[str | None] = mapped_column(Text)
    checkpoint_json: Mapped[str | None] = mapped_column(Text)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    error_type: Mapped[str | None] = mapped_column(String(64), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[str | None] = mapped_column(String(64))
    finished_at: Mapped[str | None] = mapped_column(String(64))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[str | None] = mapped_column(String(64))


class DocumentPendingTag(Base):
    __tablename__ = "document_pending_tags"

    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), primary_key=True, index=True)
    names_json: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[str | None] = mapped_column(String(64))

    document: Mapped[Document] = relationship()


class DocumentPendingCorrespondent(Base):
    __tablename__ = "document_pending_correspondents"

    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), primary_key=True, index=True)
    name: Mapped[str | None] = mapped_column(String(256))
    updated_at: Mapped[str | None] = mapped_column(String(64))

    document: Mapped[Document] = relationship()


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str | None] = mapped_column(String(256))
    color: Mapped[str | None] = mapped_column(String(32))
    is_inbox_tag: Mapped[bool | None] = mapped_column(Boolean)
    slug: Mapped[str | None] = mapped_column(String(256))
    matching_algorithm: Mapped[str | None] = mapped_column(String(64))
    is_insensitive: Mapped[bool | None] = mapped_column(Boolean)

    documents: Mapped[list[Document]] = relationship(
        secondary=document_tags, back_populates="tags"
    )


class Correspondent(Base):
    __tablename__ = "correspondents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str | None] = mapped_column(String(256))
    slug: Mapped[str | None] = mapped_column(String(256))
    matching_algorithm: Mapped[str | None] = mapped_column(String(64))
    is_insensitive: Mapped[bool | None] = mapped_column(Boolean)

    documents: Mapped[list[Document]] = relationship(back_populates="correspondent")


class DocumentType(Base):
    __tablename__ = "document_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str | None] = mapped_column(String(256))
    slug: Mapped[str | None] = mapped_column(String(256))
    matching_algorithm: Mapped[str | None] = mapped_column(String(64))
    is_insensitive: Mapped[bool | None] = mapped_column(Boolean)

    documents: Mapped[list[Document]] = relationship(back_populates="document_type")
