from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class KnowledgeDocument:
    document_id: str
    user_id: str
    course_id: str
    title: str = ""
    source_type: str = "upload"
    doc_kind: str = ""
    mime_type: str = ""
    original_filename: str = ""
    stored_path: str = ""
    parse_status: str = "pending"
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "KnowledgeDocument":
        return cls(
            document_id=str(payload.get("document_id", "")),
            user_id=str(payload.get("user_id", "")),
            course_id=str(payload.get("course_id", "")),
            title=str(payload.get("title", "")),
            source_type=str(payload.get("source_type", "upload")),
            doc_kind=str(payload.get("doc_kind", "")),
            mime_type=str(payload.get("mime_type", "")),
            original_filename=str(payload.get("original_filename", "")),
            stored_path=str(payload.get("stored_path", "")),
            parse_status=str(payload.get("parse_status", "pending")),
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", "")),
        )


@dataclass(slots=True)
class CourseCatalog:
    course_id: str
    course_name: str
    user_id: str
    summary: str = ""
    module_ids: list[str] = field(default_factory=list)
    knowledge_point_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CourseCatalog":
        return cls(
            course_id=str(payload.get("course_id", "")),
            course_name=str(payload.get("course_name", "")),
            user_id=str(payload.get("user_id", "")),
            summary=str(payload.get("summary", "")),
            module_ids=[str(item) for item in payload.get("module_ids", []) or []],
            knowledge_point_ids=[
                str(item) for item in payload.get("knowledge_point_ids", []) or []
            ],
        )


@dataclass(slots=True)
class KnowledgeChunk:
    chunk_id: str
    course_id: str
    document_id: str
    doc_kind: str = ""
    section: str = ""
    chunk_type: str = ""
    text: str = ""
    keywords: list[str] = field(default_factory=list)
    knowledge_point_ids: list[str] = field(default_factory=list)
    evidence_label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "KnowledgeChunk":
        return cls(
            chunk_id=str(payload.get("chunk_id", "")),
            course_id=str(payload.get("course_id", "")),
            document_id=str(payload.get("document_id", "")),
            doc_kind=str(payload.get("doc_kind", "")),
            section=str(payload.get("section", "")),
            chunk_type=str(payload.get("chunk_type", "")),
            text=str(payload.get("text", "")),
            keywords=[str(item) for item in payload.get("keywords", []) or []],
            knowledge_point_ids=[
                str(item) for item in payload.get("knowledge_point_ids", []) or []
            ],
            evidence_label=str(payload.get("evidence_label", "")),
        )
