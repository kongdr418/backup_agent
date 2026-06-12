from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

import numpy as np

from .config import EMBEDDING_MODEL_NAME


logger = logging.getLogger(__name__)


class EmbeddingUnavailableError(RuntimeError):
    pass


def _default_model_factory(model_name: str) -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def _normalize(values: np.ndarray) -> np.ndarray:
    matrix = np.asarray(values, dtype=np.float32)
    if matrix.ndim != 2:
        raise EmbeddingUnavailableError("embedding output must be two-dimensional")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.maximum(norms, 1e-12)


class LocalEmbeddingService:
    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL_NAME,
        model_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self.model_name = model_name
        self._model_factory = model_factory or _default_model_factory
        self._model: Any | None = None
        self._load_error: Exception | None = None
        self._load_lock = threading.Lock()

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        if self._load_error is not None:
            raise EmbeddingUnavailableError(str(self._load_error)) from self._load_error
        with self._load_lock:
            if self._model is not None:
                return self._model
            if self._load_error is not None:
                raise EmbeddingUnavailableError(str(self._load_error)) from self._load_error
            started_at = time.perf_counter()
            logger.info("[BGE] model_load_start model=%s", self.model_name)
            try:
                self._model = self._model_factory(self.model_name)
            except Exception as exc:
                self._load_error = exc
                logger.warning(
                    "[BGE] model_load_failed model=%s elapsed_ms=%d error=%s",
                    self.model_name,
                    round((time.perf_counter() - started_at) * 1000),
                    type(exc).__name__,
                )
                raise EmbeddingUnavailableError(str(exc)) from exc
            logger.info(
                "[BGE] model_load_complete model=%s elapsed_ms=%d",
                self.model_name,
                round((time.perf_counter() - started_at) * 1000),
            )
        return self._model

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        try:
            values = self._get_model().encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=False,
                show_progress_bar=False,
            )
            return _normalize(values)
        except EmbeddingUnavailableError:
            raise
        except Exception as exc:
            raise EmbeddingUnavailableError(str(exc)) from exc

    def encode_query(self, topic: str) -> np.ndarray:
        query = f"为这个课程主题检索相关教学资料：{topic.strip()}"
        matrix = self.encode_documents([query])
        return matrix[0]
