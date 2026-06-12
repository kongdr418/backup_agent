from __future__ import annotations

import json
import os
import re
import shutil
import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any

import numpy as np


_SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json_copy(value: Any, fallback: Any) -> Any:
    if not isinstance(value, type(fallback)):
        return fallback
    return json.loads(json.dumps(value, ensure_ascii=False))


class CourseKnowledgeStorage:
    def __init__(
        self,
        backend_dir: str,
        now_provider: Callable[[], str] | None = None,
    ) -> None:
        self.memory_root = os.path.join(backend_dir, "memory", "users")
        self.now_provider = now_provider or _now_iso
        self._lock = threading.RLock()

    def _safe_id(self, value: str, field_name: str) -> str:
        if not _SAFE_ID.fullmatch(value or ""):
            raise ValueError(f"invalid {field_name}")
        return value

    def _user_dir(self, user_id: str) -> str:
        return os.path.join(self.memory_root, self._safe_id(user_id, "user_id"))

    def _root_dir(self, user_id: str, create: bool = False) -> str:
        path = os.path.join(self._user_dir(user_id), "course_knowledge")
        if create:
            os.makedirs(path, exist_ok=True)
        return path

    def document_dir(self, user_id: str, document_id: str, create: bool = True) -> str:
        path = os.path.join(
            self._root_dir(user_id, create=create),
            "documents",
            self._safe_id(document_id, "document_id"),
        )
        if create:
            os.makedirs(path, exist_ok=True)
        return path

    def catalog_dir(self, user_id: str, create: bool = True) -> str:
        path = os.path.join(self._root_dir(user_id, create=create), "catalogs")
        if create:
            os.makedirs(path, exist_ok=True)
        return path

    def chunk_dir(self, user_id: str, create: bool = True) -> str:
        path = os.path.join(self._root_dir(user_id, create=create), "chunks")
        if create:
            os.makedirs(path, exist_ok=True)
        return path

    def index_dir(self, user_id: str, create: bool = True) -> str:
        path = os.path.join(self._root_dir(user_id, create=create), "indexes")
        if create:
            os.makedirs(path, exist_ok=True)
        return path

    def _document_path(self, user_id: str, document_id: str) -> str:
        return os.path.join(self.document_dir(user_id, document_id), "document.json")

    def _parsed_path(self, user_id: str, document_id: str) -> str:
        return os.path.join(self.document_dir(user_id, document_id), "parsed.json")

    def _catalog_path(self, user_id: str, course_id: str) -> str:
        return os.path.join(
            self.catalog_dir(user_id),
            f"{self._safe_id(course_id, 'course_id')}.json",
        )

    def _chunk_path(self, user_id: str, course_id: str) -> str:
        return os.path.join(
            self.chunk_dir(user_id),
            f"{self._safe_id(course_id, 'course_id')}.json",
        )

    def _course_map_path(self, user_id: str) -> str:
        return os.path.join(self.index_dir(user_id), "course_map.json")

    def _vector_matrix_path(self, user_id: str, course_id: str) -> str:
        return os.path.join(
            self.index_dir(user_id),
            f"{self._safe_id(course_id, 'course_id')}.embeddings.npy",
        )

    def _vector_metadata_path(self, user_id: str, course_id: str) -> str:
        return os.path.join(
            self.index_dir(user_id),
            f"{self._safe_id(course_id, 'course_id')}.embeddings.json",
        )

    def _read_json(self, path: str, fallback: Any) -> Any:
        if not os.path.exists(path):
            return fallback
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
        if isinstance(payload, type(fallback)):
            return payload
        return fallback

    def _write_json(self, path: str, payload: Any) -> Any:
        parent = os.path.dirname(path)
        os.makedirs(parent, exist_ok=True)
        temp_path = f"{path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
        return payload

    def save_document(
        self,
        user_id: str,
        document_id: str,
        document: dict[str, Any],
        parsed: dict[str, Any],
    ) -> None:
        self._safe_id(user_id, "user_id")
        self._safe_id(document_id, "document_id")
        document_payload = _json_copy(document, {})
        parsed_payload = _json_copy(parsed, {})
        existing = self.load_document(user_id, document_id)

        if existing and isinstance(existing.get("document"), dict):
            existing_created_at = existing["document"].get("created_at")
            if existing_created_at:
                document_payload["created_at"] = existing_created_at

        if not document_payload.get("created_at"):
            document_payload["created_at"] = self.now_provider()
        document_payload["updated_at"] = self.now_provider()

        with self._lock:
            self._write_json(self._document_path(user_id, document_id), document_payload)
            self._write_json(self._parsed_path(user_id, document_id), parsed_payload)

    def load_document(self, user_id: str, document_id: str) -> dict[str, Any] | None:
        document_path = os.path.join(
            self.document_dir(user_id, document_id, create=False),
            "document.json",
        )
        parsed_path = os.path.join(
            self.document_dir(user_id, document_id, create=False),
            "parsed.json",
        )
        if not os.path.exists(document_path) or not os.path.exists(parsed_path):
            return None
        return {
            "document": self._read_json(document_path, {}),
            "parsed": self._read_json(parsed_path, {}),
        }

    def delete_document(self, user_id: str, document_id: str) -> bool:
        directory = self.document_dir(user_id, document_id, create=False)
        if not os.path.isdir(directory):
            return False
        root = os.path.join(self._root_dir(user_id, create=False), "documents")
        abs_root = os.path.abspath(root)
        abs_dir = os.path.abspath(directory)
        if not abs_dir.startswith(abs_root + os.sep):
            raise ValueError("invalid document path")
        shutil.rmtree(abs_dir)
        return True

    def save_course_catalog(
        self,
        user_id: str,
        course_id: str,
        payload: dict[str, Any],
    ) -> None:
        self._safe_id(user_id, "user_id")
        self._safe_id(course_id, "course_id")
        with self._lock:
            self._write_json(self._catalog_path(user_id, course_id), _json_copy(payload, {}))

    def load_course_catalog(self, user_id: str, course_id: str) -> dict[str, Any] | None:
        path = os.path.join(
            self.catalog_dir(user_id, create=False),
            f"{self._safe_id(course_id, 'course_id')}.json",
        )
        if not os.path.exists(path):
            return None
        return self._read_json(path, {})

    def save_chunk_index(
        self,
        user_id: str,
        course_id: str,
        payload: list[dict[str, Any]],
    ) -> None:
        self._safe_id(user_id, "user_id")
        self._safe_id(course_id, "course_id")
        with self._lock:
            self._write_json(self._chunk_path(user_id, course_id), _json_copy(payload, []))

    def load_chunk_index(self, user_id: str, course_id: str) -> list[dict[str, Any]]:
        path = os.path.join(
            self.chunk_dir(user_id, create=False),
            f"{self._safe_id(course_id, 'course_id')}.json",
        )
        return self._read_json(path, [])

    def save_course_map(self, user_id: str, payload: dict[str, Any]) -> None:
        self._safe_id(user_id, "user_id")
        with self._lock:
            self._write_json(self._course_map_path(user_id), _json_copy(payload, {}))

    def load_course_map(self, user_id: str) -> dict[str, Any]:
        path = os.path.join(self.index_dir(user_id, create=False), "course_map.json")
        return self._read_json(path, {})

    def save_vector_index(
        self,
        user_id: str,
        course_id: str,
        metadata: dict[str, Any],
        matrix: np.ndarray,
    ) -> None:
        self._safe_id(user_id, "user_id")
        self._safe_id(course_id, "course_id")
        matrix_path = self._vector_matrix_path(user_id, course_id)
        metadata_path = self._vector_metadata_path(user_id, course_id)
        matrix_temp = f"{matrix_path}.tmp"
        metadata_temp = f"{metadata_path}.tmp"
        os.makedirs(os.path.dirname(matrix_path), exist_ok=True)
        with self._lock:
            try:
                with open(matrix_temp, "wb") as file:
                    np.save(file, np.asarray(matrix, dtype=np.float32), allow_pickle=False)
                with open(metadata_temp, "w", encoding="utf-8") as file:
                    json.dump(_json_copy(metadata, {}), file, ensure_ascii=False, indent=2)
                os.replace(matrix_temp, matrix_path)
                os.replace(metadata_temp, metadata_path)
            finally:
                for temp_path in (matrix_temp, metadata_temp):
                    if os.path.exists(temp_path):
                        os.remove(temp_path)

    def load_vector_index(
        self,
        user_id: str,
        course_id: str,
    ) -> tuple[dict[str, Any], np.ndarray] | None:
        matrix_path = os.path.join(
            self.index_dir(user_id, create=False),
            f"{self._safe_id(course_id, 'course_id')}.embeddings.npy",
        )
        metadata_path = os.path.join(
            self.index_dir(user_id, create=False),
            f"{self._safe_id(course_id, 'course_id')}.embeddings.json",
        )
        if not os.path.exists(matrix_path) or not os.path.exists(metadata_path):
            return None
        try:
            metadata = self._read_json(metadata_path, {})
            with open(matrix_path, "rb") as file:
                matrix = np.load(file, allow_pickle=False)
        except (OSError, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(matrix, np.ndarray) or matrix.ndim != 2:
            return None
        return metadata, np.asarray(matrix, dtype=np.float32)

    def delete_vector_index(self, user_id: str, course_id: str) -> bool:
        paths = (
            self._vector_matrix_path(user_id, course_id),
            self._vector_metadata_path(user_id, course_id),
        )
        removed = False
        with self._lock:
            for path in paths:
                if os.path.exists(path):
                    os.remove(path)
                    removed = True
        return removed

    def list_documents(self, user_id: str) -> list[dict[str, Any]]:
        self._safe_id(user_id, "user_id")
        root = os.path.join(self._root_dir(user_id, create=False), "documents")
        if not os.path.isdir(root):
            return []

        rows: list[dict[str, Any]] = []
        for document_id in sorted(os.listdir(root)):
            if not _SAFE_ID.fullmatch(document_id):
                continue
            loaded = self.load_document(user_id, document_id)
            if not loaded:
                continue
            rows.append(
                {
                    "document": _json_copy(loaded.get("document", {}), {}),
                    "parsed": _json_copy(loaded.get("parsed", {}), {}),
                }
            )
        rows.sort(
            key=lambda item: item.get("document", {}).get("updated_at", ""),
            reverse=True,
        )
        return rows
