from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Protocol

import numpy as np

from .storage import CourseKnowledgeStorage


logger = logging.getLogger(__name__)


INDEX_VERSION = 1


class EmbeddingService(Protocol):
    model_name: str

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        ...

    def encode_query(self, topic: str) -> np.ndarray:
        ...


def build_chunk_text(chunk: dict[str, Any]) -> str:
    keywords = "、".join(str(item) for item in chunk.get("keywords", []) if item)
    return "\n".join(
        part
        for part in (
            f"章节：{chunk.get('section', '')}".strip(),
            f"内容：{chunk.get('text', '')}".strip(),
            f"关键词：{keywords}".strip(),
        )
        if part.split("：", 1)[-1]
    )


def content_fingerprint(chunks: list[dict[str, Any]]) -> str:
    payload = [
        {
            "chunk_id": chunk.get("chunk_id", ""),
            "text": build_chunk_text(chunk),
        }
        for chunk in chunks
    ]
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _normalize_matrix(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=np.float32)
    if values.ndim != 2:
        raise ValueError("embedding matrix must be two-dimensional")
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return values / np.maximum(norms, 1e-12)


class CourseVectorIndex:
    def __init__(
        self,
        storage: CourseKnowledgeStorage,
        embedding_service: EmbeddingService,
    ) -> None:
        self.storage = storage
        self.embedding_service = embedding_service

    def rebuild(
        self,
        user_id: str,
        course_id: str,
        chunks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not chunks:
            self.delete(user_id, course_id)
            return {}
        started_at = time.perf_counter()
        logger.info(
            "[BGE] index_build_start course_id=%s chunks=%d",
            course_id,
            len(chunks),
        )
        texts = [build_chunk_text(chunk) for chunk in chunks]
        matrix = _normalize_matrix(self.embedding_service.encode_documents(texts))
        if matrix.shape[0] != len(chunks):
            raise ValueError("embedding row count does not match chunks")
        metadata = {
            "index_version": INDEX_VERSION,
            "model_name": self.embedding_service.model_name,
            "dimension": int(matrix.shape[1]),
            "chunk_ids": [str(chunk.get("chunk_id", "")) for chunk in chunks],
            "content_fingerprint": content_fingerprint(chunks),
        }
        self.storage.save_vector_index(user_id, course_id, metadata, matrix)
        logger.info(
            "[BGE] index_build_complete course_id=%s chunks=%d dimension=%d elapsed_ms=%d",
            course_id,
            len(chunks),
            int(matrix.shape[1]),
            round((time.perf_counter() - started_at) * 1000),
        )
        return metadata

    def load_valid(
        self,
        user_id: str,
        course_id: str,
        chunks: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], np.ndarray] | None:
        loaded = self.storage.load_vector_index(user_id, course_id)
        if loaded is None:
            return None
        metadata, matrix = loaded
        expected_ids = [str(chunk.get("chunk_id", "")) for chunk in chunks]
        if (
            metadata.get("index_version") != INDEX_VERSION
            or metadata.get("model_name") != self.embedding_service.model_name
            or metadata.get("chunk_ids") != expected_ids
            or metadata.get("content_fingerprint") != content_fingerprint(chunks)
            or matrix.shape[0] != len(expected_ids)
            or matrix.shape[1] != metadata.get("dimension")
        ):
            return None
        return metadata, _normalize_matrix(matrix)

    def search(
        self,
        user_id: str,
        course_id: str,
        chunks: list[dict[str, Any]],
        query_vector: np.ndarray,
    ) -> dict[str, float]:
        loaded = self.load_valid(user_id, course_id, chunks)
        if loaded is None:
            return {}
        metadata, matrix = loaded
        query = np.asarray(query_vector, dtype=np.float32).reshape(-1)
        if query.shape[0] != matrix.shape[1]:
            return {}
        query_norm = float(np.linalg.norm(query))
        if query_norm <= 1e-12:
            return {}
        scores = matrix @ (query / query_norm)
        return {
            chunk_id: float(score)
            for chunk_id, score in zip(metadata["chunk_ids"], scores, strict=True)
        }

    def query_scores(
        self,
        user_id: str,
        course_id: str,
        chunks: list[dict[str, Any]],
        topic: str,
    ) -> dict[str, float]:
        if not chunks or not topic.strip():
            return {}
        if self.load_valid(user_id, course_id, chunks) is None:
            logger.info(
                "[BGE] index_missing_or_stale course_id=%s action=skip_vector",
                course_id,
            )
            return {}
        query_vector = self.embedding_service.encode_query(topic)
        return self.search(user_id, course_id, chunks, query_vector)

    def delete(self, user_id: str, course_id: str) -> bool:
        return self.storage.delete_vector_index(user_id, course_id)
