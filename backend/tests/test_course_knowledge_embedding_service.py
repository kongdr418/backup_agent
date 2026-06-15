from __future__ import annotations

import os
import sys


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from course_knowledge.embedding_service import LocalEmbeddingService


def test_embedding_service_retries_after_load_failure():
    calls = []

    class FakeModel:
        pass

    def factory(model_name):
        calls.append(model_name)
        if len(calls) == 1:
            raise RuntimeError("temporary failure")
        return FakeModel()

    service = LocalEmbeddingService(model_name="test-model", model_factory=factory)

    try:
        service._get_model()
    except Exception as exc:
        assert "temporary failure" in str(exc)

    assert isinstance(service._get_model(), FakeModel)
    assert calls == ["test-model", "test-model"]
