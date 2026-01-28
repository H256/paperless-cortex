from __future__ import annotations

from pydantic import BaseModel


class DocumentNoteIn(BaseModel):
    id: int
    note: str | None = None
    created: str | None = None
    user: dict | None = None


class DocumentIn(BaseModel):
    id: int
    title: str | None = None
    content: str | None = None
    correspondent: int | None = None
    document_type: int | None = None
    document_date: str | None = None
    created: str | None = None
    modified: str | None = None
    added: str | None = None
    deleted_at: str | None = None
    archive_serial_number: int | None = None
    original_file_name: str | None = None
    mime_type: str | None = None
    page_count: int | None = None
    owner: int | None = None
    user_can_change: bool | None = None
    is_shared_by_requester: bool | None = None
    notes: list[DocumentNoteIn] = []
    tags: list[int] = []


class TagIn(BaseModel):
    id: int
    name: str | None = None
    color: str | None = None
    is_inbox_tag: bool | None = None
    slug: str | None = None
    matching_algorithm: int | str | None = None
    is_insensitive: bool | None = None


class CorrespondentIn(BaseModel):
    id: int
    name: str | None = None
    slug: str | None = None
    matching_algorithm: int | str | None = None
    is_insensitive: bool | None = None


class DocumentTypeIn(BaseModel):
    id: int
    name: str | None = None
    slug: str | None = None
    matching_algorithm: int | str | None = None
    is_insensitive: bool | None = None
