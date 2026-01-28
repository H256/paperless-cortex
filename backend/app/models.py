from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table, Text
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
    deleted_at: Mapped[str | None] = mapped_column(String(64))

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
    chunk_count: Mapped[int | None] = mapped_column(Integer)


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
